#!/usr/bin/env python3
"""
EPP_Verdict — Premier run ESMM live
====================================
Script unifié : backup, diagnostic, run, vérification, rapport.
Usage : python first_live_run.py [--question "..."] [--models m1,m2,m3] [--dry-run]
"""

import asyncio
import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path for imports
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
os.chdir(_project_root)  # Ensure CWD is project root for DB_PATH / schema.sql

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

DEFAULT_QUESTION = "What is the difference between proof of work and proof of stake?"
DEFAULT_MODELS = ["mistral:latest", "llama3.1:8b", "deepseek-r1:latest"]
DB_PATH = "data/epp.db"
BACKUP_DIR = "data/backups"
REPORT_DIR = "reports"
TIMEOUT_SECONDS = 900  # 15 min max pour un run complet

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("first_live_run")


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def section(title: str):
    log.info(f"\n{'='*60}\n  {title}\n{'='*60}")


def check(label: str, ok: bool, detail: str = ""):
    status = "✅" if ok else "❌"
    msg = f"  {status} {label}"
    if detail:
        msg += f" — {detail}"
    log.info(msg)
    return ok


# ---------------------------------------------------------------------------
# PHASE 0 — BACKUP
# ---------------------------------------------------------------------------

def phase_0_backup() -> str | None:
    section("PHASE 0 — Backup DB")

    if not Path(DB_PATH).exists():
        log.info(f"  Pas de DB existante ({DB_PATH}) — premier run, pas de backup.")
        return None

    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{BACKUP_DIR}/epp_backup_{ts}.db"
    shutil.copy2(DB_PATH, backup_path)
    size_mb = Path(backup_path).stat().st_size / (1024 * 1024)
    log.info(f"  Backup : {backup_path} ({size_mb:.2f} MB)")
    return backup_path


# ---------------------------------------------------------------------------
# PHASE 1 — PRE-FLIGHT
# ---------------------------------------------------------------------------

async def phase_1_preflight(models: list[str]) -> bool:
    section("PHASE 1 — Pré-vol")
    all_ok = True

    # 1a. Imports
    try:
        from services.esmm.pipeline import run_pipeline  # noqa: F401
        from services.esmm.orchestrator import ESMMOrchestrator  # noqa: F401
        from services.esmm.consensus_engine import ConsensusEngine  # noqa: F401
        all_ok &= check("Imports pipeline", True)
    except Exception as e:
        all_ok &= check("Imports pipeline", False, str(e))
        return False

    # 1b. model_weights dans compute_consensus
    import inspect
    sig = inspect.signature(ConsensusEngine.compute_consensus)
    has_mw = "model_weights" in sig.parameters
    all_ok &= check("model_weights dans compute_consensus", has_mw)

    # 1c. Schema DB
    try:
        import sqlite3
        conn = sqlite3.connect(":memory:")
        schema_path = Path("database/schema.sql")
        if not schema_path.exists():
            schema_path = Path("schema.sql")
        conn.executescript(schema_path.read_text())

        cursor = conn.execute("PRAGMA table_info(attestations)")
        cols = [row[1] for row in cursor.fetchall()]
        for col in ["adjusted_consensus_score", "diversity_bonus_factor", "commit_reveal_verified"]:
            all_ok &= check(f"Colonne attestations.{col}", col in cols)

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='commit_reveal'"
        )
        all_ok &= check("Table commit_reveal", cursor.fetchone() is not None)
        conn.close()
    except Exception as e:
        all_ok &= check("Schema DB", False, str(e))

    # 1d. Ollama connecté + modèles disponibles
    try:
        from services.providers.ollama import OllamaProvider

        for model in models:
            provider = OllamaProvider(model=model, timeout=30.0)
            health = await provider.health_check()
            connected = health.get("connected", False)
            all_ok &= check(f"Ollama {model}", connected,
                          f"latency={health.get('latency_ms', '?')}ms" if connected else "NOT CONNECTED")
            if hasattr(provider, 'close'):
                await provider.close()
    except Exception as e:
        all_ok &= check("Ollama health", False, str(e))

    # 1e. Vérifier que les modèles couvrent ≥2 familles architecturales
    try:
        from services.providers.base import infer_architecture_family
        families = {m: infer_architecture_family(m) for m in models}
        unique_families = set(families.values()) - {"unknown"}
        detail = ", ".join(f"{m}={f}" for m, f in families.items())
        all_ok &= check(
            f"Diversité architecturale ({len(unique_families)} familles)",
            len(unique_families) >= 2,
            detail,
        )
    except Exception as e:
        all_ok &= check("Architecture families", False, str(e))

    return all_ok


# ---------------------------------------------------------------------------
# PHASE 2 — RUN ESMM
# ---------------------------------------------------------------------------

async def phase_2_run(question: str, models: list[str], dry_run: bool = False) -> dict:
    section("PHASE 2 — Run ESMM" + (" (DRY RUN)" if dry_run else ""))

    if dry_run:
        log.info("  Mode dry-run : pas d'exécution réelle.")
        return {"status": "dry_run", "question": question, "models": models}

    log.info(f"  Question : {question}")
    log.info(f"  Modèles  : {', '.join(models)}")
    log.info(f"  Timeout  : {TIMEOUT_SECONDS}s")
    log.info("")

    start = time.time()

    try:
        from services.esmm.pipeline import run_pipeline
        from services.esmm.orchestrator import ESMMRunConfig
        from database.engine import ISpaceDB

        # Initialiser la DB
        db = ISpaceDB(DB_PATH)
        await db.initialize()

        # Config ESMM réduite pour run live (éviter timeout)
        esmm_cfg = ESMMRunConfig(
            models=models,
            cycles_per_type={"divergent": 2, "debate": 2, "meta": 1},
            max_total_cycles=8,
            adaptive_cycles=False,
        )

        # Lancer le pipeline
        result = await asyncio.wait_for(
            run_pipeline(
                question=question,
                db=db,
                models=models,
                esmm_config=esmm_cfg,
            ),
            timeout=TIMEOUT_SECONDS,
        )

        duration = time.time() - start
        log.info(f"\n  ⏱  Durée : {duration:.1f}s")

        # Extraire les infos clés du résultat
        run_info = {
            "status": "success",
            "duration_seconds": round(duration, 1),
            "question": question,
            "models": models,
        }

        # Adapter selon le type de retour
        if hasattr(result, "__dict__"):
            for attr in ["run_id", "triplets_extracted", "attestations_created",
                        "consensus_triplets", "total_cycles"]:
                if hasattr(result, attr):
                    val = getattr(result, attr)
                    if hasattr(val, "__len__"):
                        run_info[attr] = len(val)
                    else:
                        run_info[attr] = val
        elif isinstance(result, dict):
            run_info.update({k: v for k, v in result.items()
                          if isinstance(v, (int, float, str, bool))})

        for k, v in run_info.items():
            if k != "status":
                log.info(f"  {k}: {v}")

        from database.pool import close_pool
        await close_pool()
        return run_info

    except asyncio.TimeoutError:
        duration = time.time() - start
        log.error(f"  ❌ TIMEOUT après {duration:.1f}s (limite: {TIMEOUT_SECONDS}s)")
        log.error("  Causes probables :")
        log.error("    - Un modèle ne répond pas (Ollama surchargé / modèle trop gros)")
        log.error("    - Boucle infinie dans les cycles ESMM")
        log.error("  Action : relancer avec --verbose ou réduire à 2 modèles")
        return {"status": "timeout", "duration_seconds": round(duration, 1)}

    except Exception as e:
        duration = time.time() - start
        log.error(f"  ❌ ERREUR après {duration:.1f}s : {type(e).__name__}: {e}")

        # Diagnostic contextuel
        error_str = str(e).lower()
        if "connection" in error_str or "refused" in error_str:
            log.error("  → Ollama n'est probablement pas lancé. Vérifier : ollama serve")
        elif "notimplementederror" in error_str:
            log.error("  → Code mock non remplacé. Vérifier le traceback pour identifier le fichier.")
        elif "keyerror" in error_str:
            log.error("  → Clé manquante — possible désync entre signatures R-2.1.1")
        elif "timeout" in error_str:
            log.error("  → Un modèle met trop de temps. Essayer avec des modèles plus petits.")
        elif "import" in error_str or "module" in error_str:
            log.error("  → Import cassé. Vérifier PYTHONPATH et structure des modules.")
        else:
            import traceback
            log.error(f"  Traceback complet :\n{traceback.format_exc()}")

        return {"status": "error", "error": str(e), "duration_seconds": round(duration, 1)}


# ---------------------------------------------------------------------------
# PHASE 3 — VÉRIFICATION POST-RUN
# ---------------------------------------------------------------------------

async def _query_scalar(db, sql: str) -> int:
    """Helper: execute a scalar query via db.connection() context manager."""
    async with db.connection() as conn:
        cursor = await conn.execute(sql)
        row = await cursor.fetchone()
        return row[0] if row else 0


async def phase_3_verify(run_info: dict) -> dict:
    section("PHASE 3 — Vérification post-run")

    if run_info.get("status") != "success":
        log.info(f"  Skipped — run status: {run_info.get('status')}")
        return {"verification": "skipped"}

    results = {}

    try:
        from database.engine import ISpaceDB
        from database.pool import close_pool

        db = ISpaceDB(DB_PATH)
        await db.initialize()

        # 3a. Attestations produites
        try:
            count = await _query_scalar(db, "SELECT COUNT(*) FROM attestations")
            check("Attestations en DB", count > 0, f"{count} attestation(s)")
            results["attestations_count"] = count
        except Exception as e:
            check("Attestations en DB", False, str(e))

        # 3b. Graphe enrichi
        try:
            concepts = await _query_scalar(db, "SELECT COUNT(*) FROM concepts WHERE is_active=1")
            relations = await _query_scalar(db, "SELECT COUNT(*) FROM relations WHERE is_active=1")
            check("Graphe enrichi", concepts > 0, f"{concepts} concepts, {relations} relations")
            results["concepts"] = concepts
            results["relations"] = relations
        except Exception as e:
            check("Graphe enrichi", False, str(e))

        # 3c. Track record (votes enregistrés)
        try:
            votes = await _query_scalar(db, "SELECT COUNT(*) FROM model_track_record")
            check("Votes model_track_record", votes > 0, f"{votes} vote(s)")
            results["votes_recorded"] = votes
        except Exception as e:
            check("Votes track_record", False, str(e))

        # 3d. Commit-reveal (si R-2.2.3 actif)
        try:
            commits = await _query_scalar(db, "SELECT COUNT(*) FROM commit_reveal")
            check("Commit-reveal hashes", commits > 0, f"{commits} commit(s)")
            results["commits_stored"] = commits
        except Exception as e:
            check("Commit-reveal", False, str(e))

        # 3e. Diversity bonus calculé
        try:
            async with db.connection() as conn:
                cursor = await conn.execute(
                    "SELECT diversity_bonus_factor FROM attestations ORDER BY attestation_id DESC LIMIT 1"
                )
                row = await cursor.fetchone()
            if row:
                factor = row[0]
                check("Diversity bonus", True, f"factor={factor}")
                results["diversity_bonus_factor"] = factor
            else:
                check("Diversity bonus", False, "no attestations")
        except Exception as e:
            check("Diversity bonus", False, str(e))

        await close_pool()

    except Exception as e:
        log.error(f"  Erreur vérification : {e}")
        results["error"] = str(e)

    return results


# ---------------------------------------------------------------------------
# PHASE 4 — RAPPORT
# ---------------------------------------------------------------------------

def phase_4_report(backup_path: str | None, run_info: dict, verify_info: dict, args):
    section("PHASE 4 — Rapport")

    report = {
        "timestamp": datetime.now().isoformat(),
        "question": args.question,
        "models": args.models.split(","),
        "backup": backup_path,
        "run": run_info,
        "verification": verify_info,
    }

    # Sauvegarder le rapport
    Path(REPORT_DIR).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"{REPORT_DIR}/live_run_{ts}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    log.info(f"  Rapport sauvegardé : {report_path}")

    # Résumé
    status = run_info.get("status", "unknown")
    duration = run_info.get("duration_seconds", "?")

    log.info(f"\n{'='*60}")
    if status == "success":
        log.info(f"  🟢 RUN RÉUSSI — {duration}s")
        log.info(f"  Attestations : {verify_info.get('attestations_count', '?')}")
        log.info(f"  Graphe : {verify_info.get('concepts', '?')} concepts, {verify_info.get('relations', '?')} relations")
        log.info(f"  Votes : {verify_info.get('votes_recorded', '?')}")
        log.info(f"  Commits : {verify_info.get('commits_stored', '?')}")
        log.info(f"\n  Prochaine étape : lancer une campagne de 10-20 questions variées.")
    elif status == "dry_run":
        log.info(f"  🔵 DRY RUN — tout est prêt, relancer sans --dry-run")
    elif status == "timeout":
        log.info(f"  🔴 TIMEOUT — {duration}s. Réduire les modèles ou augmenter le timeout.")
    else:
        log.info(f"  🔴 ERREUR — {run_info.get('error', 'voir logs ci-dessus')}")
        if backup_path:
            log.info(f"  Restaurer la DB : cp {backup_path} {DB_PATH}")
    log.info(f"{'='*60}\n")

    return report_path


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

async def main():
    global TIMEOUT_SECONDS

    parser = argparse.ArgumentParser(description="EPP_Verdict — Premier run ESMM live")
    parser.add_argument(
        "--question", "-q",
        default=DEFAULT_QUESTION,
        help=f"Question à soumettre (default: '{DEFAULT_QUESTION[:50]}...')",
    )
    parser.add_argument(
        "--models", "-m",
        default=",".join(DEFAULT_MODELS),
        help=f"Modèles Ollama, séparés par virgules (default: {','.join(DEFAULT_MODELS)})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Vérifier le pré-vol sans lancer le run",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=TIMEOUT_SECONDS,
        help=f"Timeout en secondes (default: {TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Activer les logs DEBUG",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    TIMEOUT_SECONDS = args.timeout

    models = [m.strip() for m in args.models.split(",")]

    log.info(f"EPP_Verdict — First Live Run")
    log.info(f"Date    : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info(f"Question: {args.question}")
    log.info(f"Models  : {', '.join(models)}")

    # Phase 0 — Backup
    backup_path = phase_0_backup()

    # Phase 1 — Pré-vol
    preflight_ok = await phase_1_preflight(models)
    if not preflight_ok:
        log.error("\n  ❌ Pré-vol échoué. Corriger les erreurs ci-dessus avant de lancer.")
        phase_4_report(backup_path, {"status": "preflight_failed"}, {}, args)
        sys.exit(1)

    # Phase 2 — Run
    run_info = await phase_2_run(args.question, models, dry_run=args.dry_run)

    # Phase 3 — Vérification
    verify_info = await phase_3_verify(run_info)

    # Phase 4 — Rapport
    report_path = phase_4_report(backup_path, run_info, verify_info, args)

    sys.exit(0 if run_info.get("status") in ("success", "dry_run") else 1)


if __name__ == "__main__":
    asyncio.run(main())
