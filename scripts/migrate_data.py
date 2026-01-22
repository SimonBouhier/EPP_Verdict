#!/usr/bin/env python3
"""
LYRA CLEAN - CSV TO SQLITE MIGRATION
====================================

ETL script to transform legacy CSV files into optimized SQLite database.

Usage:
    python scripts/migrate_data.py --edges ../data/graphs/edges.csv --nodes ../data/graphs/nodes.csv

Author: Refactored from Lyra_Uni_3 legacy
"""
from __future__ import annotations

import argparse
import asyncio
import pandas as pd
import time
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.engine import ISpaceDB


async def migrate_concepts(db: ISpaceDB, nodes_csv: str) -> int:
    """
    Migrate nodes.csv → concepts table.

    Args:
        db: Database engine
        nodes_csv: Path to nodes.csv

    Returns:
        Number of concepts inserted

    CSV Format:
        node,rho
        entropy,0.82
        milk,0.99
    """
    print(f"\n[1/2] Migrating concepts from {nodes_csv}...")

    # Load CSV with pandas (last time we use it!)
    df = pd.read_csv(nodes_csv)

    required_cols = {'node', 'rho'}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Missing columns in nodes.csv. Expected: {required_cols}, Got: {set(df.columns)}")

    # Prepare batch insert
    concepts = []
    for _, row in df.iterrows():
        concepts.append((
            row['node'],           # id
            float(row['rho']),     # rho_static
            0,                     # degree (will be computed from relations)
            time.time(),           # created_at
            None,                  # last_accessed
            0                      # access_count
        ))

    # Batch insert (much faster than row-by-row)
    async with db.connection() as conn:
        await conn.executemany(
            """
            INSERT OR REPLACE INTO concepts (id, rho_static, degree, created_at, last_accessed, access_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            concepts
        )
        await conn.commit()

    print(f"✅ Inserted {len(concepts)} concepts")
    return len(concepts)


async def migrate_relations(db: ISpaceDB, edges_csv: str) -> int:
    """
    Migrate edges.csv → relations table.

    Args:
        db: Database engine
        edges_csv: Path to edges.csv

    Returns:
        Number of relations inserted

    CSV Format:
        src,dst,weight,kappa
        entropy,information,0.85,0.62
        milk,toppings,0.92,0.71
    """
    print(f"\n[2/2] Migrating relations from {edges_csv}...")

    # Load CSV
    df = pd.read_csv(edges_csv)

    required_cols = {'src', 'dst', 'weight', 'kappa'}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Missing columns in edges.csv. Expected: {required_cols}, Got: {set(df.columns)}")

    # Prepare batch insert
    relations = []
    for _, row in df.iterrows():
        relations.append((
            row['src'],            # source
            row['dst'],            # target
            float(row['weight']),  # weight
            float(row['kappa']),   # kappa
            time.time()            # created_at
        ))

    # Batch insert
    async with db.connection() as conn:
        await conn.executemany(
            """
            INSERT OR REPLACE INTO relations (source, target, weight, kappa, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            relations
        )
        await conn.commit()

    print(f"✅ Inserted {len(relations)} relations")
    return len(relations)


async def compute_degrees(db: ISpaceDB) -> None:
    """
    Compute node degrees from relations table.

    Updates concepts.degree column (used for importance ranking).
    """
    print(f"\n[3/3] Computing concept degrees...")

    async with db.connection() as conn:
        # Count outgoing edges per concept
        await conn.execute(
            """
            UPDATE concepts
            SET degree = (
                SELECT COUNT(*)
                FROM relations
                WHERE relations.source = concepts.id
            )
            """
        )
        await conn.commit()

    print(f"✅ Degrees computed")


async def verify_migration(db: ISpaceDB) -> None:
    """
    Verify migration integrity.

    Checks:
    - Concepts count > 0
    - Relations count > 0
    - All relations reference valid concepts
    - Indexes exist
    """
    print(f"\n[VERIFICATION] Checking migration integrity...")

    async with db.connection() as conn:
        # Check concepts
        cursor = await conn.execute("SELECT COUNT(*) FROM concepts")
        concept_count = (await cursor.fetchone())[0]
        print(f"  • Concepts: {concept_count}")

        if concept_count == 0:
            raise ValueError("❌ No concepts found after migration!")

        # Check relations
        cursor = await conn.execute("SELECT COUNT(*) FROM relations")
        relation_count = (await cursor.fetchone())[0]
        print(f"  • Relations: {relation_count}")

        if relation_count == 0:
            raise ValueError("❌ No relations found after migration!")

        # Check referential integrity
        cursor = await conn.execute(
            """
            SELECT COUNT(*)
            FROM relations r
            WHERE NOT EXISTS (SELECT 1 FROM concepts WHERE id = r.source)
               OR NOT EXISTS (SELECT 1 FROM concepts WHERE id = r.target)
            """
        )
        orphan_count = (await cursor.fetchone())[0]

        if orphan_count > 0:
            print(f"  ⚠️  Warning: {orphan_count} relations reference non-existent concepts")
        else:
            print(f"  • Referential integrity: ✅ OK")

        # Check indexes
        cursor = await conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'index' AND name LIKE 'idx_%'
            """
        )
        indexes = await cursor.fetchall()
        print(f"  • Indexes: {len(indexes)} created")

        # Sample query performance
        start = time.time()
        cursor = await conn.execute(
            """
            SELECT target, weight FROM relations
            WHERE source = (SELECT id FROM concepts ORDER BY RANDOM() LIMIT 1)
            ORDER BY weight DESC LIMIT 20
            """
        )
        await cursor.fetchall()
        query_time_ms = (time.time() - start) * 1000

        print(f"  • Sample neighbor query: {query_time_ms:.2f}ms")

        if query_time_ms > 50:
            print(f"    ⚠️  Slow query detected! Expected < 50ms")

    print("\n✅ Migration verified successfully!")


async def main():
    """Main migration workflow."""
    parser = argparse.ArgumentParser(
        description="Migrate Lyra CSV data to SQLite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate from default locations
  python scripts/migrate_data.py \\
    --edges ../data/graphs/edges.csv \\
    --nodes ../data/graphs/nodes.csv

  # Specify custom output database
  python scripts/migrate_data.py \\
    --edges edges.csv \\
    --nodes nodes.csv \\
    --output custom.db
        """
    )

    parser.add_argument(
        '--edges',
        required=True,
        help='Path to edges.csv file'
    )

    parser.add_argument(
        '--nodes',
        required=True,
        help='Path to nodes.csv file'
    )

    parser.add_argument(
        '--output',
        default='data/ispace.db',
        help='Output SQLite database path (default: data/ispace.db)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing database'
    )

    args = parser.parse_args()

    # Check input files
    edges_path = Path(args.edges)
    nodes_path = Path(args.nodes)

    if not edges_path.exists():
        print(f"❌ Error: edges.csv not found at {edges_path}")
        sys.exit(1)

    if not nodes_path.exists():
        print(f"❌ Error: nodes.csv not found at {nodes_path}")
        sys.exit(1)

    # Check output database
    db_path = Path(args.output)
    if db_path.exists() and not args.force:
        response = input(f"⚠️  Database {db_path} already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Migration cancelled.")
            sys.exit(0)
        db_path.unlink()

    # ========================================================================
    # MIGRATION WORKFLOW
    # ========================================================================

    print("="*80)
    print(" LYRA CLEAN - CSV TO SQLITE MIGRATION")
    print("="*80)
    print(f"Input:")
    print(f"  • Nodes: {nodes_path}")
    print(f"  • Edges: {edges_path}")
    print(f"Output:")
    print(f"  • Database: {db_path}")
    print("="*80)

    start_time = time.time()

    # Initialize database
    db = ISpaceDB(str(db_path))
    await db.initialize()

    # Run migration steps
    concept_count = await migrate_concepts(db, str(nodes_path))
    relation_count = await migrate_relations(db, str(edges_path))
    await compute_degrees(db)

    # Verify
    await verify_migration(db)

    # Optimize
    print(f"\n[OPTIMIZATION] Running VACUUM + ANALYZE...")
    await db.vacuum()

    # Final stats
    elapsed = time.time() - start_time
    stats = await db.get_stats()

    print("\n" + "="*80)
    print(" MIGRATION COMPLETE")
    print("="*80)
    print(f"Total time: {elapsed:.2f}s")
    print(f"\nDatabase statistics:")
    for key, value in stats.items():
        print(f"  • {key}: {value}")
    print("="*80)

    print(f"\n🎉 Success! Database ready at: {db_path}")
    print(f"\nNext steps:")
    print(f"  1. Test neighbor queries: await db.get_neighbors('entropy', limit=10)")
    print(f"  2. Start the server: python app/main.py")
    print(f"  3. Delete old CSV files (they're now obsolete)")


if __name__ == "__main__":
    asyncio.run(main())
