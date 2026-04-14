#!/usr/bin/env python3
"""
build_lyra_edges_nodes.py
Build a weighted co-occurrence graph from a JSONL corpus.
Computes simplified Ollivier-Ricci curvature for each edge.
Respects segment boundaries (newlines/bullets) so that beta texts
(isolated bullet points) produce sparser graphs than alpha prose.

Outputs:
  --out-edges  edges CSV  (word1, word2, weight, weight_alpha, weight_beta, curvature)
  --out-nodes  nodes CSV  (word, freq, weighted_degree)
"""
import argparse, csv, json, re, sys
from collections import Counter
from pathlib import Path

# ── Stopwords ──────────────────────────────────────────────────────────────
STOPWORDS = {
    "the","a","an","in","of","to","and","or","is","are","was","were","be","been",
    "being","have","has","had","do","does","did","will","would","could","should",
    "may","might","shall","can","it","its","this","that","these","those","by",
    "from","with","at","for","as","on","but","not","if","than","then","when",
    "which","who","what","how","all","any","both","each","few","more","most",
    "other","some","such","no","nor","so","yet","either","neither","while",
    "although","because","since","unless","until","about","above","after","before",
    "between","into","through","during","under","over","their","they","our","we",
    "you","he","she","them","us","my","your","his","her","very","just","also",
    "only","one","two","three","four","five","six","seven","eight","nine","ten",
    "first","second","third","rather","quite","well","where","here","there","now",
    "then","therefore","however","moreover","thus","hence","re","per","vs","via",
    "can","put","its","also","each","does","even","must","make","take","give",
    "many","much","every","still","often","always","never","always","around",
    "within","without","across","among","along","upon","same","different",
}


def clean_token(w: str) -> str:
    return re.sub(r"[^a-z0-9_\-]", "", w.lower())


def tokenize_to_segments(text: str) -> list:
    """
    Split text into segments at newline boundaries, then tokenize each segment.
    This is the key design choice: bullet-point beta texts (one concept per line)
    produce many single-token segments with no inter-bullet co-occurrences,
    whereas alpha prose (one long paragraph) produces one dense segment.
    """
    segments = []
    for line in re.split(r"[\n\r]+", text):
        line = re.sub(r"^[\s\-\*\•\·]+", "", line).strip()
        if not line:
            continue
        tokens = [clean_token(w) for w in line.split()]
        tokens = [t for t in tokens if len(t) >= 3 and t not in STOPWORDS]
        if tokens:
            segments.append(tokens)
    return segments


def extract_texts(record: dict, fields: list) -> list:
    texts = []
    for field in fields:
        val = record.get(field)
        if val is None:
            continue
        if isinstance(val, str):
            texts.append(val)
        elif isinstance(val, dict):
            texts.extend(v for v in val.values() if isinstance(v, str))
        elif isinstance(val, list):
            texts.extend(v for v in val if isinstance(v, str))
    return texts


def build_cooccurrence(records: list, fields: list, window: int):
    edge_all   = Counter()
    edge_alpha = Counter()
    edge_beta  = Counter()
    word_freq  = Counter()

    for record in records:
        condition = record.get("condition", "all")
        for text in extract_texts(record, fields):
            segments = tokenize_to_segments(text)
            for seg in segments:
                for tok in seg:
                    word_freq[tok] += 1
                for i in range(len(seg)):
                    for j in range(i + 1, min(i + window, len(seg))):
                        edge = tuple(sorted([seg[i], seg[j]]))
                        edge_all[edge] += 1
                        if condition == "alpha":
                            edge_alpha[edge] += 1
                        elif condition == "beta":
                            edge_beta[edge] += 1

    return edge_all, edge_alpha, edge_beta, word_freq


def compute_curvature(edges: dict, node_degrees: dict) -> dict:
    """
    Simplified Ollivier-Ricci curvature:
      κ(u,v) = 2·T(u,v) / (d_u + d_v - 2·w_uv) - 1
    where T(u,v) = Σ_{c ∈ N(u)∩N(v)} min(w(u,c), w(v,c))
    Positive κ: many shared neighbors (clustered, semantic cohesion).
    Negative κ: few shared neighbors (tree-like, semantic fragmentation).
    """
    adj: dict = {}
    for (u, v), w in edges.items():
        adj.setdefault(u, {})[v] = w
        adj.setdefault(v, {})[u] = w

    curvatures = {}
    for (u, v), w_uv in edges.items():
        d_u = node_degrees.get(u, 1.0)
        d_v = node_degrees.get(v, 1.0)
        common = set(adj.get(u, {}).keys()) & set(adj.get(v, {}).keys())
        T_uv = sum(min(adj[u].get(c, 0), adj[v].get(c, 0)) for c in common)
        denom = d_u + d_v - 2 * w_uv
        curvatures[(u, v)] = (2.0 * T_uv / denom - 1.0) if denom > 0 else 0.0

    return curvatures


def main():
    p = argparse.ArgumentParser(description="Build co-occurrence graph from JSONL corpus.")
    p.add_argument("--jsonl",    required=True)
    p.add_argument("--fields",   nargs="+", default=["responses"])
    p.add_argument("--lang",     default="en")
    p.add_argument("--topv",     type=int, default=2000)
    p.add_argument("--min-freq", type=int, default=2)
    p.add_argument("--window",   type=int, default=3)
    p.add_argument("--compute-curvature", action="store_true")
    p.add_argument("--out-edges", required=True)
    p.add_argument("--out-nodes", required=True)
    args = p.parse_args()

    print("=" * 60)
    print("build_lyra_edges_nodes.py - kappa-Risk Graph Builder")
    print("=" * 60)
    print(f"  JSONL    : {args.jsonl}")
    print(f"  Fields   : {args.fields}")
    print(f"  Window   : {args.window}  topV={args.topv}  min-freq={args.min_freq}")

    records = []
    with open(args.jsonl, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    n_alpha = sum(1 for r in records if r.get("condition") == "alpha")
    n_beta  = sum(1 for r in records if r.get("condition") == "beta")
    print(f"  Records  : {len(records)} (α={n_alpha}, β={n_beta})")

    edge_all, edge_alpha, edge_beta, word_freq = build_cooccurrence(
        records, args.fields, args.window
    )

    # Select top vocabulary
    top_words = {w for w, _ in word_freq.most_common(args.topv)}
    print(f"  Vocab    : {len(word_freq)} unique tokens → top {len(top_words)} selected")

    # Filter edges by vocab and min-freq
    def filter_edges(counter):
        return {
            (u, v): w for (u, v), w in counter.items()
            if u in top_words and v in top_words and w >= args.min_freq
        }

    edges = filter_edges(edge_all)
    e_alpha = filter_edges(edge_alpha)
    e_beta  = filter_edges(edge_beta)

    print(f"  Edges    : {len(edges)} total | α={len(e_alpha)} | β={len(e_beta)}")

    # Weighted degree
    node_degrees: dict = {}
    for (u, v), w in edges.items():
        node_degrees[u] = node_degrees.get(u, 0) + w
        node_degrees[v] = node_degrees.get(v, 0) + w

    # Curvature
    curvatures: dict = {}
    if args.compute_curvature:
        print("  Computing Ollivier-Ricci curvature...")
        curvatures = compute_curvature(edges, node_degrees)
        kn = sum(1 for k in curvatures.values() if k < 0)
        kp = len(curvatures) - kn
        frac = kn / len(curvatures) if curvatures else 0
        print(f"  kappa < 0: {kn:4d}  ({frac:.1%})")
        print(f"  kappa >= 0: {kp:4d}  ({1-frac:.1%})")

        # Per-condition breakdown
        for cname, cdict in [("alpha", e_alpha), ("beta", e_beta)]:
            if not cdict:
                print(f"  [{cname}]  no edges after filtering")
                continue
            kvals = [curvatures.get((u, v), curvatures.get((v, u), 0.0))
                     for (u, v) in cdict]
            kn_c  = sum(1 for k in kvals if k < 0)
            frac_c = kn_c / len(kvals)
            avg_k  = sum(kvals) / len(kvals)
            print(f"  [{cname}]  edges={len(cdict)}  kappa_neg={frac_c:.3f}  kappa_mean={avg_k:+.3f}")

    # ── Write edges CSV ────────────────────────────────────────────────────
    all_nodes = set()
    for u, v in edges:
        all_nodes.add(u); all_nodes.add(v)

    with open(args.out_edges, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["word1", "word2", "weight", "weight_alpha", "weight_beta", "curvature"])
        for (u, v), w in sorted(edges.items(), key=lambda x: -x[1]):
            ka = edge_alpha.get((u, v), edge_alpha.get((v, u), 0))
            kb = edge_beta.get((u, v), edge_beta.get((v, u), 0))
            kappa = curvatures.get((u, v), curvatures.get((v, u), 0.0))
            wr.writerow([u, v, w, ka, kb, round(kappa, 6)])

    # ── Write nodes CSV ────────────────────────────────────────────────────
    with open(args.out_nodes, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["word", "freq", "weighted_degree"])
        for node in sorted(all_nodes):
            wr.writerow([node, word_freq.get(node, 0), node_degrees.get(node, 0)])

    print(f"\nSaved : {args.out_edges}  ({len(edges)} edges)")
    print(f"Saved : {args.out_nodes}  ({len(all_nodes)} nodes)")
    print("=" * 60)


if __name__ == "__main__":
    main()
