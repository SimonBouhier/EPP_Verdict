"""
EPP Embedding Migration Tool
============================
Migrates concept embeddings from one model to another.
Uses EmbeddingProvider interface — no hardcoded model or dimension.

Usage:
    python tools/migrate_embeddings.py --to nomic-embed-text --batch-size 50
    python tools/migrate_embeddings.py --to mxbai-embed-large --dry-run
    python tools/migrate_embeddings.py --finalize <migration_id>
    python tools/migrate_embeddings.py --rollback <migration_id>
    python tools/migrate_embeddings.py --status <migration_id>

Phases:
    1. PREPARE: Check provider, count concepts, create migration entry
    2. MIGRATE: Re-embed concepts, write to concept_embeddings (idempotent)
    3. FINALIZE: Copy to concepts.embedding (separate command)

Author: EPP-Verdict Team
Phase: 0.2.3
"""
import argparse
import asyncio
import json
import struct
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.engine import ISpaceDB
from services.providers.registry import ProviderRegistry
from services.providers.base import EmbeddingProvider


# ============================================================================
# HELPERS
# ============================================================================

def serialize_embedding(vec: List[float]) -> bytes:
    """Serialize embedding to float32 blob."""
    return struct.pack(f'{len(vec)}f', *vec)


async def get_embedding_provider(model_id: str) -> Optional[EmbeddingProvider]:
    """
    Get embedding provider for model from registry.

    Falls back to creating OllamaEmbeddingProvider if not registered.
    """
    provider = ProviderRegistry.get_embedding_provider(model_id)
    if provider:
        return provider

    # Try to create OllamaEmbeddingProvider
    try:
        from services.providers.ollama_embeddings import OllamaEmbeddingProvider
        provider = OllamaEmbeddingProvider(model_id=model_id)
        ProviderRegistry.register_embedding_provider(model_id, provider)
        return provider
    except Exception as e:
        print(f"[ERROR] Cannot create provider for {model_id}: {e}")
        return None


# ============================================================================
# MIGRATION CLASS
# ============================================================================

class EmbeddingMigrator:
    """
    Handles progressive embedding migration with full traceability.
    """

    def __init__(
        self,
        db: ISpaceDB,
        target_model: str,
        batch_size: int = 50,
        dry_run: bool = False
    ):
        self.db = db
        self.target_model = target_model
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.provider: Optional[EmbeddingProvider] = None
        self.migration_id: Optional[int] = None
        self.errors: List[Dict[str, str]] = []

    async def prepare(self) -> bool:
        """
        Phase 1: PREPARE
        - Check provider health
        - Count concepts to migrate
        - Create migration entry
        """
        print(f"\n{'='*60}")
        print(f"PHASE 1: PREPARE")
        print(f"{'='*60}")

        # Get provider
        self.provider = await get_embedding_provider(self.target_model)
        if not self.provider:
            print(f"[ERROR] No provider available for model: {self.target_model}")
            return False

        # Get dimension
        dimension = self.provider.get_dimension()
        print(f"[INFO] Provider: {self.provider.get_provider_id()}")
        print(f"[INFO] Model: {self.target_model}")
        print(f"[INFO] Dimension: {dimension}")

        # Count concepts needing migration
        concepts_to_migrate = await self.db.get_concepts_needing_migration(
            self.target_model, limit=999999
        )
        total_concepts = len(concepts_to_migrate)
        print(f"[INFO] Concepts to migrate: {total_concepts}")

        if total_concepts == 0:
            print("[INFO] No concepts need migration. All embeddings are up to date.")
            return False

        if self.dry_run:
            print(f"[DRY-RUN] Would migrate {total_concepts} concepts")
            return False

        # Determine source model (from existing concepts)
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT DISTINCT embedding_model FROM concepts WHERE embedding IS NOT NULL LIMIT 1"
            )
            row = await cursor.fetchone()
            source_model = row[0] if row else "unknown"

            # Get source dimension
            cursor = await conn.execute(
                "SELECT length(embedding) FROM concepts WHERE embedding IS NOT NULL LIMIT 1"
            )
            row = await cursor.fetchone()
            source_dim = (row[0] // 4) if row else 0

        # Create migration entry
        self.migration_id = await self.db.create_embedding_migration(
            from_model=source_model,
            to_model=self.target_model,
            dim_from=source_dim,
            dim_to=dimension,
            triggered_by="cli"
        )
        print(f"[INFO] Migration ID: {self.migration_id}")

        # Update total count
        await self.db.update_embedding_migration(
            self.migration_id,
            concepts_total=total_concepts
        )

        return True

    async def migrate(self) -> Dict[str, int]:
        """
        Phase 2: MIGRATE
        - For each batch of concepts:
          - Embed via provider
          - Write to concept_embeddings
          - Update migration progress
        """
        print(f"\n{'='*60}")
        print(f"PHASE 2: MIGRATE")
        print(f"{'='*60}")

        if self.migration_id is None:
            print("[ERROR] No migration ID. Run prepare() first.")
            return {"migrated": 0, "failed": 0}

        dimension = self.provider.get_dimension()
        migrated = 0
        failed = 0

        while True:
            # Get batch of concepts needing migration
            concepts = await self.db.get_concepts_needing_migration(
                self.target_model, limit=self.batch_size
            )

            if not concepts:
                break

            print(f"\n[BATCH] Processing {len(concepts)} concepts...")

            for concept_id in concepts:
                try:
                    # Generate embedding
                    embedding_vec = await self.provider.embed(concept_id)

                    if not embedding_vec or len(embedding_vec) != dimension:
                        raise ValueError(f"Invalid embedding dimension: {len(embedding_vec) if embedding_vec else 0}")

                    # Serialize and store
                    embedding_blob = serialize_embedding(embedding_vec)
                    await self.db.store_concept_embedding(
                        concept_id=concept_id,
                        model_id=self.target_model,
                        dimension=dimension,
                        embedding=embedding_blob
                    )

                    migrated += 1
                    print(f"  [OK] {concept_id[:50]}")

                except Exception as e:
                    failed += 1
                    error_entry = {"concept_id": concept_id, "error": str(e)}
                    self.errors.append(error_entry)
                    print(f"  [FAIL] {concept_id[:50]} - {e}")

                # Update progress periodically
                if (migrated + failed) % 10 == 0:
                    await self.db.update_embedding_migration(
                        self.migration_id,
                        concepts_migrated=migrated,
                        concepts_failed=failed
                    )

        # Final update
        await self.db.update_embedding_migration(
            self.migration_id,
            concepts_migrated=migrated,
            concepts_failed=failed,
            error_log=json.dumps(self.errors) if self.errors else None,
            status="completed" if failed == 0 else "failed"
        )

        print(f"\n[RESULT] Migrated: {migrated}, Failed: {failed}")
        return {"migrated": migrated, "failed": failed}


# ============================================================================
# CLI COMMANDS
# ============================================================================

async def cmd_migrate(args):
    """Run migration to target model."""
    db = ISpaceDB(args.db_path)
    await db.initialize()

    try:
        migrator = EmbeddingMigrator(
            db=db,
            target_model=args.to,
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )

        if await migrator.prepare():
            result = await migrator.migrate()

            if result["failed"] == 0:
                print(f"\n[SUCCESS] Migration complete!")
                print(f"[HINT] Run: python tools/migrate_embeddings.py --finalize {migrator.migration_id}")
            else:
                print(f"\n[WARNING] Migration completed with {result['failed']} failures.")
                print(f"[HINT] Check migration status: python tools/migrate_embeddings.py --status {migrator.migration_id}")
    finally:
        if db._pool:
            from database.pool import close_pool
            await close_pool()


async def cmd_finalize(args):
    """Finalize migration by copying to concepts.embedding."""
    db = ISpaceDB(args.db_path)
    await db.initialize()

    try:
        migration = await db.get_embedding_migration(args.finalize)
        if not migration:
            print(f"[ERROR] Migration {args.finalize} not found")
            return

        print(f"[INFO] Finalizing migration {args.finalize}")
        print(f"[INFO] From: {migration['from_model']} -> To: {migration['to_model']}")
        print(f"[INFO] Status: {migration['status']}")
        print(f"[INFO] Migrated: {migration['concepts_migrated']}, Failed: {migration['concepts_failed']}")

        if migration['concepts_failed'] > 0:
            print(f"[ERROR] Cannot finalize: {migration['concepts_failed']} concepts failed")
            return

        if args.dry_run:
            print(f"[DRY-RUN] Would update concepts.embedding with {migration['to_model']} embeddings")
            return

        updated = await db.finalize_embedding_migration(
            args.finalize,
            migration['to_model']
        )
        print(f"[SUCCESS] Updated {updated} concepts to {migration['to_model']}")
    finally:
        if db._pool:
            from database.pool import close_pool
            await close_pool()


async def cmd_rollback(args):
    """Rollback a migration."""
    db = ISpaceDB(args.db_path)
    await db.initialize()

    try:
        migration = await db.get_embedding_migration(args.rollback)
        if not migration:
            print(f"[ERROR] Migration {args.rollback} not found")
            return

        print(f"[INFO] Rolling back migration {args.rollback}")
        print(f"[INFO] Will delete {migration['to_model']} embeddings from concept_embeddings")

        if args.dry_run:
            print(f"[DRY-RUN] Would rollback migration {args.rollback}")
            return

        deleted = await db.rollback_embedding_migration(args.rollback)
        print(f"[SUCCESS] Deleted {deleted} embeddings, migration marked as rolled_back")
    finally:
        if db._pool:
            from database.pool import close_pool
            await close_pool()


async def cmd_status(args):
    """Show migration status."""
    db = ISpaceDB(args.db_path)
    await db.initialize()

    try:
        migration = await db.get_embedding_migration(args.status)
        if not migration:
            print(f"[ERROR] Migration {args.status} not found")
            return

        print(f"\n{'='*60}")
        print(f"MIGRATION STATUS: {args.status}")
        print(f"{'='*60}")
        print(f"From Model:      {migration['from_model']} ({migration['dimension_from']}D)")
        print(f"To Model:        {migration['to_model']} ({migration['dimension_to']}D)")
        print(f"Status:          {migration['status']}")
        print(f"Triggered By:    {migration['triggered_by']}")
        print(f"Concepts Total:  {migration['concepts_total']}")
        print(f"Migrated:        {migration['concepts_migrated']}")
        print(f"Failed:          {migration['concepts_failed']}")

        if migration.get('error_log'):
            errors = migration['error_log']
            print(f"\nErrors ({len(errors)}):")
            for err in errors[:5]:
                print(f"  - {err['concept_id'][:40]}: {err['error'][:50]}")
            if len(errors) > 5:
                print(f"  ... and {len(errors) - 5} more")
    finally:
        if db._pool:
            from database.pool import close_pool
            await close_pool()


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="EPP Embedding Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate to nomic-embed-text
  python tools/migrate_embeddings.py --to nomic-embed-text

  # Dry run (show what would be done)
  python tools/migrate_embeddings.py --to nomic-embed-text --dry-run

  # Finalize a migration
  python tools/migrate_embeddings.py --finalize 1

  # Rollback a migration
  python tools/migrate_embeddings.py --rollback 1

  # Check migration status
  python tools/migrate_embeddings.py --status 1
"""
    )

    parser.add_argument("--to", type=str, help="Target embedding model")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size (default: 50)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--finalize", type=int, help="Finalize migration by ID")
    parser.add_argument("--rollback", type=int, help="Rollback migration by ID")
    parser.add_argument("--status", type=int, help="Show migration status by ID")
    parser.add_argument("--db-path", type=str, default="data/ispace.db", help="Database path")

    args = parser.parse_args()

    # Determine which command to run
    if args.finalize:
        asyncio.run(cmd_finalize(args))
    elif args.rollback:
        asyncio.run(cmd_rollback(args))
    elif args.status:
        asyncio.run(cmd_status(args))
    elif args.to:
        asyncio.run(cmd_migrate(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
