#!/usr/bin/env python3
"""
LYRA ESMM - CLI Tool
====================

Outil en ligne de commande pour gerer les runs ESMM.

Usage:
    python scripts/esmm_cli.py run [--quick|--full|--models M1,M2]
    python scripts/esmm_cli.py status <run_id>
    python scripts/esmm_cli.py result <run_id>
    python scripts/esmm_cli.py pause <run_id>
    python scripts/esmm_cli.py resume <run_id>
    python scripts/esmm_cli.py metrics
    python scripts/esmm_cli.py gaps [--type isolated|unstable|bridge]
    python scripts/esmm_cli.py watch <run_id>  # Mode surveillance temps reel

Author: Lyra-ACE ESMM Protocol
"""
import argparse
import json
import sys
import time
from typing import Optional
import urllib.request
import urllib.error

API_URL = "http://127.0.0.1:8000"


def api_call(method: str, endpoint: str, data: dict = None) -> dict:
    """Effectue un appel API."""
    url = f"{API_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}

    try:
        if data:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode('utf-8'),
                headers=headers,
                method=method
            )
        else:
            req = urllib.request.Request(url, headers=headers, method=method)

        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"Erreur HTTP {e.code}: {error_body}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Erreur de connexion: {e.reason}")
        print(f"Assurez-vous que le serveur est lance: start_server.bat")
        sys.exit(1)


def print_json(data: dict, indent: int = 2):
    """Affiche du JSON formate."""
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def cmd_run(args):
    """Lance un run ESMM."""
    # Configuration par defaut
    cycles = {"divergent": 3, "debate": 2, "meta": 1}

    if args.quick:
        cycles = {"divergent": 1, "debate": 1, "meta": 1}
        print("Mode QUICK: 1 cycle de chaque type")
    elif args.full:
        cycles = {"divergent": 5, "debate": 3, "meta": 2}
        print("Mode FULL: 5 divergent, 3 debate, 2 meta")
    elif args.cycles:
        parts = args.cycles.split(",")
        if len(parts) == 3:
            cycles = {
                "divergent": int(parts[0]),
                "debate": int(parts[1]),
                "meta": int(parts[2])
            }

    # Modeles
    models = ["mistral", "gpt-oss:20b"]
    if args.models:
        models = [m.strip() for m in args.models.split(",")]

    payload = {
        "models": models,
        "seed_type": args.seed or "standard",
        "cycles_per_type": cycles,
        "min_consensus": 0.5,
        "adaptive_cycles": not args.no_adaptive,
        "detect_gaps": True,
        "build_cochain": True
    }

    print(f"\nLancement du run ESMM...")
    print(f"  Modeles: {', '.join(models)}")
    print(f"  Cycles: {cycles}")
    print()

    result = api_call("POST", "/graph/esmm-run", payload)
    print_json(result)

    run_id = result.get("run_id")
    if run_id and args.watch:
        print(f"\nSurveillance du run #{run_id}...")
        cmd_watch_internal(run_id)


def cmd_status(args):
    """Affiche le statut d'un run."""
    result = api_call("GET", f"/graph/esmm-run/{args.run_id}")
    print_json(result)


def cmd_result(args):
    """Affiche le resultat d'un run."""
    result = api_call("GET", f"/graph/esmm-run/{args.run_id}/result")
    print_json(result)

    # Afficher un resume
    print("\n--- Resume ---")
    print(f"Status: {result.get('status')}")
    print(f"Cycles: {result.get('cycles_completed')}")
    print(f"Triplets: {result.get('total_triplets')} extraits, {result.get('triplets_injected')} injectes")
    print(f"Cochaine: {result.get('cochain_size')} entrees")
    print(f"Lacunes: {result.get('gaps_detected')}")
    print(f"Coverage: {result.get('coverage_score', 0):.2%}")
    print(f"Duree: {result.get('duration_ms', 0)/1000:.1f}s")


def cmd_pause(args):
    """Met en pause un run."""
    result = api_call("POST", f"/graph/esmm-run/{args.run_id}/pause")
    print_json(result)


def cmd_resume(args):
    """Reprend un run."""
    result = api_call("POST", f"/graph/esmm-run/{args.run_id}/resume")
    print_json(result)


def cmd_cycles(args):
    """Affiche les cycles d'un run."""
    params = f"?limit={args.limit or 20}"
    if args.type:
        params += f"&cycle_type={args.type}"
    result = api_call("GET", f"/graph/esmm-run/{args.run_id}/cycles{params}")
    print_json(result)


def cmd_metrics(args):
    """Affiche les metriques de couverture."""
    result = api_call("GET", "/graph/coverage/metrics")
    print_json(result)

    print("\n--- Resume ---")
    print(f"Coverage Score: {result.get('coverage_score', 0):.2%}")
    print(f"Consensus Density: {result.get('consensus_density', 0):.2%}")
    print(f"Epistemic Diversity: {result.get('epistemic_diversity', 0):.2%}")
    print(f"Structural Stability: {result.get('structural_stability', 0):.2%}")
    print(f"Graph Density: {result.get('graph_density', 0):.4f}")
    print(f"Isolated Ratio: {result.get('isolated_ratio', 0):.2%}")


def cmd_gaps(args):
    """Affiche les lacunes actives."""
    params = f"?limit={args.limit or 30}"
    if args.type:
        params += f"&gap_type={args.type}"
    result = api_call("GET", f"/graph/gaps/active{params}")

    if isinstance(result, list):
        print(f"Lacunes actives: {len(result)}")
        for gap in result:
            priority = gap.get('priority', 0)
            gtype = gap.get('gap_type', '?')
            details = gap.get('details', {})
            question = gap.get('suggested_question', '')[:60]
            print(f"  [{gtype:10}] P={priority:.2f} - {question}...")
    else:
        print_json(result)


def cmd_cochain(args):
    """Affiche les stats de la cochaine."""
    result = api_call("GET", "/graph/cochain/stats")
    print_json(result)


def cmd_watch_internal(run_id: int, interval: int = 5):
    """Surveille un run en temps reel (interne)."""
    prev_cycles = 0

    while True:
        try:
            result = api_call("GET", f"/graph/esmm-run/{run_id}")

            status = result.get('status', '?')
            cycles = result.get('cycles_completed', 0)
            progress = result.get('progress_percent', 0)
            current = result.get('current_cycle', '-')
            iteration = result.get('current_iteration', 0)

            # Afficher la mise a jour
            if cycles != prev_cycles or status in ('completed', 'failed'):
                timestamp = time.strftime("%H:%M:%S")
                print(f"[{timestamp}] {status:10} | Cycles: {cycles:2} | Progress: {progress:5.1f}% | Current: {current}/{iteration}")
                prev_cycles = cycles

            if status in ('completed', 'failed', 'paused'):
                print(f"\nRun termine avec status: {status}")
                break

            time.sleep(interval)

        except KeyboardInterrupt:
            print("\nSurveillance arretee")
            break


def cmd_watch(args):
    """Surveille un run en temps reel."""
    print(f"Surveillance du run #{args.run_id} (Ctrl+C pour arreter)")
    print("-" * 60)
    cmd_watch_internal(args.run_id, args.interval or 5)


def main():
    parser = argparse.ArgumentParser(
        description="LYRA ESMM - CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python scripts/esmm_cli.py run --quick
  python scripts/esmm_cli.py run --models llama3.1:8b,mistral:7b --watch
  python scripts/esmm_cli.py status 1
  python scripts/esmm_cli.py result 1
  python scripts/esmm_cli.py watch 1
  python scripts/esmm_cli.py metrics
  python scripts/esmm_cli.py gaps --type bridge
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Commande")

    # run
    p_run = subparsers.add_parser("run", help="Lance un run ESMM")
    p_run.add_argument("--quick", action="store_true", help="Mode rapide (1 cycle de chaque)")
    p_run.add_argument("--full", action="store_true", help="Mode complet (5,3,2 cycles)")
    p_run.add_argument("--cycles", help="Cycles personnalises: divergent,debate,meta")
    p_run.add_argument("--models", help="Modeles: m1,m2")
    p_run.add_argument("--seed", default="standard", help="Type de graine")
    p_run.add_argument("--no-adaptive", action="store_true", help="Desactiver l'adaptation")
    p_run.add_argument("--watch", "-w", action="store_true", help="Surveiller apres lancement")
    p_run.set_defaults(func=cmd_run)

    # status
    p_status = subparsers.add_parser("status", help="Statut d'un run")
    p_status.add_argument("run_id", type=int, help="ID du run")
    p_status.set_defaults(func=cmd_status)

    # result
    p_result = subparsers.add_parser("result", help="Resultat d'un run")
    p_result.add_argument("run_id", type=int, help="ID du run")
    p_result.set_defaults(func=cmd_result)

    # pause
    p_pause = subparsers.add_parser("pause", help="Met en pause un run")
    p_pause.add_argument("run_id", type=int, help="ID du run")
    p_pause.set_defaults(func=cmd_pause)

    # resume
    p_resume = subparsers.add_parser("resume", help="Reprend un run")
    p_resume.add_argument("run_id", type=int, help="ID du run")
    p_resume.set_defaults(func=cmd_resume)

    # cycles
    p_cycles = subparsers.add_parser("cycles", help="Liste les cycles d'un run")
    p_cycles.add_argument("run_id", type=int, help="ID du run")
    p_cycles.add_argument("--type", help="Type de cycle: divergent, debate, meta")
    p_cycles.add_argument("--limit", type=int, default=20, help="Nombre max")
    p_cycles.set_defaults(func=cmd_cycles)

    # metrics
    p_metrics = subparsers.add_parser("metrics", help="Metriques de couverture")
    p_metrics.set_defaults(func=cmd_metrics)

    # gaps
    p_gaps = subparsers.add_parser("gaps", help="Lacunes actives")
    p_gaps.add_argument("--type", help="Type: isolated, unstable, bridge")
    p_gaps.add_argument("--limit", type=int, default=30, help="Nombre max")
    p_gaps.set_defaults(func=cmd_gaps)

    # cochain
    p_cochain = subparsers.add_parser("cochain", help="Stats de la cochaine")
    p_cochain.set_defaults(func=cmd_cochain)

    # watch
    p_watch = subparsers.add_parser("watch", help="Surveille un run en temps reel")
    p_watch.add_argument("run_id", type=int, help="ID du run")
    p_watch.add_argument("--interval", "-i", type=int, default=5, help="Intervalle (secondes)")
    p_watch.set_defaults(func=cmd_watch)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
