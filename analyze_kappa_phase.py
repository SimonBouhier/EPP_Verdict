#!/usr/bin/env python3
"""
analyze_kappa_phase.py
Phase detection on Betti curves: find κ_c (critical curvature threshold),
compute Δβ₀, Δβ₁, hole_density, and write enriched CSV + markdown report.

Input:
  --csv   kappa_betti.csv from run_kappa_topology_on_lyra.py

Outputs:
  --out-prefix  <prefix>_metrics.csv   enriched table
                <prefix>_report.md     markdown report with κ_c ±2 rows
"""
import argparse, csv, math
from pathlib import Path


def read_betti(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "kappa0": float(row["kappa0"]),
                "nV":     int(row["nV"]),
                "nE":     int(row["nE"]),
                "nT":     int(row["nT"]),
                "b0":     int(row["b0"]),
                "b1":     int(row["b1"]),
            })
    return rows


def enrich(rows):
    """Add Δβ₀, Δβ₁, score, hole_density columns."""
    enriched = []
    for i, r in enumerate(rows):
        nV = r["nV"]
        nE = r["nE"]
        b0 = r["b0"]
        b1 = r["b1"]

        # Δ columns: change from previous row (finite difference)
        if i == 0:
            db0 = 0
            db1 = 0
        else:
            db0 = r["b0"] - rows[i - 1]["b0"]
            db1 = r["b1"] - rows[i - 1]["b1"]

        # score: combined fragmentation signal
        # high b0 (many components) AND high b1 (many holes) → high score
        score = (b0 + b1) / max(nV, 1)

        # hole_density: cycles per edge
        hole_density = b1 / max(nE, 1)

        enriched.append({**r, "db0": db0, "db1": db1, "score": round(score, 6),
                         "hole_density": round(hole_density, 6)})
    return enriched


def find_critical_point(enriched):
    """
    κ_c = threshold where |Δβ₀| is maximal (largest jump in connected components).
    This marks the phase transition: graph fragmenting as κ₀ increases.
    """
    if not enriched:
        return None
    # Skip first row (db0=0 by definition)
    best_i = max(range(1, len(enriched)), key=lambda i: abs(enriched[i]["db0"]),
                 default=0)
    return best_i


def write_metrics_csv(enriched, path):
    if not enriched:
        return
    fieldnames = list(enriched[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=fieldnames)
        wr.writeheader()
        wr.writerows(enriched)


def write_report_md(enriched, kc_idx, out_path):
    lines = []
    lines.append("# κ-Risk Phase Analysis Report\n")

    if not enriched:
        lines.append("No data.\n")
        out_path.write_text("\n".join(lines), encoding="utf-8")
        return

    kc = enriched[kc_idx]["kappa0"]
    lines.append(f"## Critical threshold κ_c = {kc:.4f}\n")
    lines.append("The critical threshold marks the largest jump in β₀ (connected components),\n")
    lines.append("indicating where the semantic graph undergoes phase fragmentation.\n\n")

    # Summary stats
    first = enriched[0]
    last  = enriched[-1]
    lines.append("## Summary\n")
    lines.append(f"| Metric | κ₀ = {first['kappa0']:.3f} (min) | κ₀ = {last['kappa0']:.3f} (max) |\n")
    lines.append("|--------|------|------|\n")
    lines.append(f"| Vertices (nV) | {first['nV']} | {last['nV']} |\n")
    lines.append(f"| Edges (nE) | {first['nE']} | {last['nE']} |\n")
    lines.append(f"| β₀ (components) | {first['b0']} | {last['b0']} |\n")
    lines.append(f"| β₁ (cycles) | {first['b1']} | {last['b1']} |\n")
    lines.append(f"| score | {first['score']:.4f} | {last['score']:.4f} |\n")
    lines.append(f"| hole_density | {first['hole_density']:.4f} | {last['hole_density']:.4f} |\n\n")

    # Context around κ_c (±2 rows)
    lo = max(0, kc_idx - 2)
    hi = min(len(enriched), kc_idx + 3)
    context = enriched[lo:hi]

    lines.append(f"## κ_c context (rows {lo}–{hi-1})\n\n")
    lines.append("| κ₀ | nV | nE | nT | β₀ | β₁ | Δβ₀ | Δβ₁ | score | hole_density |\n")
    lines.append("|-----|----|----|----|----|----|----|-----|-------|------|\n")
    for r in context:
        marker = " ← κ_c" if r["kappa0"] == kc else ""
        lines.append(
            f"| {r['kappa0']:.4f} | {r['nV']} | {r['nE']} | {r['nT']} | {r['b0']} | {r['b1']} "
            f"| {r['db0']:+d} | {r['db1']:+d} | {r['score']:.4f} | {r['hole_density']:.4f} |{marker}\n"
        )
    lines.append("\n")

    # Full table
    lines.append("## Full Betti curve\n\n")
    lines.append("| κ₀ | nV | nE | nT | β₀ | β₁ | score |\n")
    lines.append("|-----|----|----|----|----|-----|-------|\n")
    for r in enriched:
        marker = " ←" if r["kappa0"] == kc else ""
        lines.append(
            f"| {r['kappa0']:.4f} | {r['nV']} | {r['nE']} | {r['nT']} | "
            f"{r['b0']} | {r['b1']} | {r['score']:.4f} |{marker}\n"
        )

    out_path.write_text("".join(lines), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description="Phase detection on Betti curves.")
    p.add_argument("--csv",        required=True)
    p.add_argument("--out-prefix", required=True)
    args = p.parse_args()

    print("=" * 60)
    print("analyze_kappa_phase.py - Phase Detection")
    print("=" * 60)
    print(f"  Input  : {args.csv}")
    print(f"  Prefix : {args.out_prefix}")

    rows = read_betti(args.csv)
    print(f"  Loaded : {len(rows)} rows")

    enriched = enrich(rows)
    kc_idx = find_critical_point(enriched)

    if kc_idx is not None:
        kc = enriched[kc_idx]["kappa0"]
        print(f"  κ_c    : {kc:.4f}  (row {kc_idx}, Δβ₀={enriched[kc_idx]['db0']:+d})")

    metrics_path = Path(f"{args.out_prefix}_metrics.csv")
    report_path  = Path(f"{args.out_prefix}_report.md")

    write_metrics_csv(enriched, metrics_path)
    write_report_md(enriched, kc_idx if kc_idx is not None else 0, report_path)

    print(f"\nSaved : {metrics_path}")
    print(f"Saved : {report_path}")
    print("=" * 60)

    # Print report to stdout
    print("\n" + "─" * 60)
    print(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
