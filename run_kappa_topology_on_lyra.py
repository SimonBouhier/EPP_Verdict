#!/usr/bin/env python3
"""
run_kappa_topology_on_lyra.py
κ-sweep: filter the co-occurrence graph at successive curvature thresholds κ₀
and compute Betti numbers β₀, β₁ at each step.

Inputs:
  --edges  edges CSV from build_lyra_edges_nodes.py  (word1, word2, weight, ..., curvature)
  --nodes  nodes CSV from build_lyra_edges_nodes.py  (word, freq, weighted_degree)

Output:
  --out-csv  kappa_betti.csv  (kappa0, nV, nE, nT, b0, b1)
"""
import argparse, csv, sys
from collections import defaultdict


def read_edges(path):
    edges = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            edges.append({
                "u": row["word1"],
                "v": row["word2"],
                "w": float(row["weight"]),
                "kappa": float(row["curvature"]),
            })
    return edges


def read_nodes(path):
    nodes = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nodes.append(row["word"])
    return nodes


class UnionFind:
    def __init__(self, items):
        self.parent = {x: x for x in items}
        self.rank   = {x: 0 for x in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1

    def components(self):
        return len({self.find(x) for x in self.parent})


def count_triangles(active_edges, adj):
    """Count triangles among active edges."""
    triangles = 0
    # for each edge (u,v), count common neighbors w where (u,w) and (v,w) also active
    edge_set = set()
    for u, v in active_edges:
        edge_set.add((u, v))
        edge_set.add((v, u))

    counted = set()
    for u, v in active_edges:
        for w in adj.get(u, set()) & adj.get(v, set()):
            tri = tuple(sorted([u, v, w]))
            if tri not in counted:
                counted.add(tri)
                triangles += 1
    return triangles


def sweep(all_edges, all_nodes, kappa_thresholds, include_triangles):
    results = []

    for kappa0 in kappa_thresholds:
        # Filter edges with kappa >= kappa0
        active = [(e["u"], e["v"]) for e in all_edges if e["kappa"] >= kappa0]

        # Nodes that appear in active edges
        active_nodes = set()
        for u, v in active:
            active_nodes.add(u)
            active_nodes.add(v)

        nV = len(active_nodes)
        nE = len(active)

        if nV == 0:
            results.append({
                "kappa0": kappa0, "nV": 0, "nE": 0, "nT": 0, "b0": 0, "b1": 0
            })
            continue

        # β₀ via Union-Find
        uf = UnionFind(active_nodes)
        for u, v in active:
            uf.union(u, v)
        b0 = uf.components()

        # Triangles
        nT = 0
        if include_triangles:
            adj = defaultdict(set)
            for u, v in active:
                adj[u].add(v)
                adj[v].add(u)
            nT = count_triangles(active, adj)

        # β₁ = E - V + β₀  (Euler characteristic for simplicial complex)
        b1 = nE - nV + b0

        results.append({
            "kappa0": round(kappa0, 6),
            "nV": nV,
            "nE": nE,
            "nT": nT,
            "b0": b0,
            "b1": max(0, b1),
        })

    return results


def main():
    p = argparse.ArgumentParser(description="κ-sweep: Betti curves over curvature thresholds.")
    p.add_argument("--edges",           required=True)
    p.add_argument("--nodes",           required=True)
    p.add_argument("--kappa-start",     type=float, default=-0.5)
    p.add_argument("--kappa-end",       type=float, default=0.7)
    p.add_argument("--kappa-steps",     type=int,   default=20)
    p.add_argument("--include-triangles", action="store_true")
    p.add_argument("--out-csv",         required=True)
    args = p.parse_args()

    print("=" * 60)
    print("run_kappa_topology_on_lyra.py - kappa-Sweep")
    print("=" * 60)
    print(f"  Edges  : {args.edges}")
    print(f"  Nodes  : {args.nodes}")
    print(f"  kappa range: [{args.kappa_start}, {args.kappa_end}] in {args.kappa_steps} steps")
    print(f"  Triangles: {args.include_triangles}")

    all_edges = read_edges(args.edges)
    all_nodes = read_nodes(args.nodes)
    print(f"  Loaded : {len(all_edges)} edges, {len(all_nodes)} nodes")

    # Build threshold list
    step = (args.kappa_end - args.kappa_start) / max(args.kappa_steps - 1, 1)
    thresholds = [round(args.kappa_start + i * step, 6) for i in range(args.kappa_steps)]

    print(f"\n{'kappa0':>10}  {'nV':>6}  {'nE':>6}  {'nT':>6}  {'b0':>5}  {'b1':>5}")
    print("-" * 50)

    results = sweep(all_edges, all_nodes, thresholds, args.include_triangles)

    for r in results:
        print(f"  {r['kappa0']:>8.4f}  {r['nV']:>6}  {r['nE']:>6}  {r['nT']:>6}  {r['b0']:>5}  {r['b1']:>5}")

    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=["kappa0", "nV", "nE", "nT", "b0", "b1"])
        wr.writeheader()
        wr.writerows(results)

    print(f"\nSaved : {args.out_csv}  ({len(results)} rows)")
    print("=" * 60)


if __name__ == "__main__":
    main()
