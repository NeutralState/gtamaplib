#!/usr/bin/env python3
"""
circular_deps.py - READ-ONLY (Chantier B, etapes B1+B2).

Construit le graphe de dependance cam->cam B-strict COMPLET (toutes cams, pas
seulement la descente depuis les leaks), puis detecte les composantes fortement
connexes (Tarjan). Une SCC de taille >1 = cycle ou des poses se valident
mutuellement. Classe chaque cycle:
  - SAIN  : contient au moins une leak cam (ancrage ground-truth dans la boucle)
  - PUR   : aucune leak -> auto-referentiel, suspect, besoin d'un ancrage externe

Arete C -> B (C depend de B): il existe un LM L tel que C marque L en tier
anchor/high ET B est dans L.source_cameras. (definition B-strict, reutilisee
telle quelle depuis audit_leak_influence_tree.build_indices.)

Reutilise load_data, build_indices, is_leak de audit_leak_influence_tree.
Optionnellement dump le graphe d'adjacence (--dump-graph).
AUCUNE ECRITURE par defaut (stdout seulement). Progress sur stderr.

Usage:
    python3 tools/audit/circular_deps.py
    python3 tools/audit/circular_deps.py --dump-graph
    python3 tools/audit/circular_deps.py --min-scc 2
"""

import argparse
import json
import os
import sys
from collections import defaultdict

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)

import audit_leak_influence_tree as L

GEN_DIR = os.path.join(os.path.dirname(THIS_DIR), 'generated')
GRAPH_OUT = os.path.join(GEN_DIR, 'dep_graph.json')


def build_full_graph(cameras, cam_to_anchor_marks, lm_to_sources):
    """Graphe dirige complet C -> {B}. Exclut les cams D/X comme sources."""
    excluded = set()
    for name, d in cameras.items():
        if not isinstance(d, dict):
            continue
        if L.is_leak(d):
            cc = (d.get('constraint_class') or '')
            if cc.startswith('D') or cc.startswith('X'):
                excluded.add(name)
    adj = defaultdict(set)
    for c, lms in cam_to_anchor_marks.items():
        if c in excluded:
            continue
        for lm in lms:
            for b in lm_to_sources.get(lm, []):
                if b == c or b in excluded:
                    continue
                adj[c].add(b)
    return {k: sorted(v) for k, v in adj.items()}, excluded


def tarjan_scc(adj):
    """SCC iteratif (Tarjan). adj: dict node -> list[node]. Retourne list[list]."""
    index = {}
    low = {}
    on_stack = {}
    stack = []
    sccs = []
    counter = [0]
    nodes = set(adj) | {b for vs in adj.values() for b in vs}

    def strongconnect(v):
        work = [(v, 0)]
        while work:
            node, pi = work[-1]
            if pi == 0:
                index[node] = low[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                on_stack[node] = True
            recursed = False
            succs = adj.get(node, [])
            for j in range(pi, len(succs)):
                w = succs[j]
                if w not in index:
                    work[-1] = (node, j + 1)
                    work.append((w, 0))
                    recursed = True
                    break
                elif on_stack.get(w):
                    low[node] = min(low[node], index[w])
            if recursed:
                continue
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    comp.append(w)
                    if w == node:
                        break
                sccs.append(comp)
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])

    for v in nodes:
        if v not in index:
            strongconnect(v)
    return sccs


def main():
    ap = argparse.ArgumentParser(description="READ-ONLY: detecte les cycles du graphe de dependance cam->cam (B).")
    ap.add_argument('--dump-graph', action='store_true',
                    help=f"Ecrit le graphe d'adjacence dans {GRAPH_OUT}.")
    ap.add_argument('--min-scc', type=int, default=2,
                    help="Taille minimale de SCC a reporter (defaut 2).")
    args = ap.parse_args()

    print("Chargement + build_indices (B-strict)...", file=sys.stderr)
    cameras, landmarks, pixels, lm_tiers = L.load_data()
    # CYCLE-DETECT-FIX (2026-07-09): les LM demotees par TIERS-SIGMA comptent
    # encore comme anchor/high pour les ARETES de dependance — la demotion
    # retire leur poids BA, pas la realite de la dependance. Sans ca, une
    # demotion (qui depend des covariances du dernier solve) peut MASQUER un
    # cycle pur du detecteur. Deterministe donne les data.
    try:
        import json as _json
        _full = _json.load(open('tools/generated/confidence_tiers.json'))
        _lmrec = _full.get('landmarks', _full.get('lms', {}))
        for _n, _r in _lmrec.items():
            if str(_r.get('reason', '')).startswith('TIERS-SIGMA demotion'):
                lm_tiers[_n] = 'high'
    except Exception:
        pass
    lm_to_sources, cam_to_sourced, lm_to_anchor_markers, cam_to_anchor_marks = \
        L.build_indices(cameras, landmarks, pixels, lm_tiers)

    adj, excluded = build_full_graph(cameras, cam_to_anchor_marks, lm_to_sources)
    n_nodes = len(set(adj) | {b for vs in adj.values() for b in vs})
    n_edges = sum(len(v) for v in adj.values())
    leaks = {n for n, d in cameras.items() if isinstance(d, dict) and L.is_leak(d)}

    print(f"# Graphe B-strict: {n_nodes} noeuds, {n_edges} aretes, "
          f"{len(excluded)} cams D/X exclues, {len(leaks)} leaks")

    if args.dump_graph:
        with open(GRAPH_OUT, 'w') as f:
            json.dump({'meta': {'nodes': n_nodes, 'edges': n_edges,
                                'definition': 'B-strict cam->cam, D/X excluded'},
                       'adjacency': adj}, f, indent=2)
        print(f"# graphe dumpe: {GRAPH_OUT}")

    sccs = [c for c in tarjan_scc(adj) if len(c) >= args.min_scc]
    sccs.sort(key=len, reverse=True)

    # ANCHOR-CRITERION-V2 (2026-07-09): trois classes au lieu de deux.
    #   SAIN         : leak DANS la boucle (ancrage ground-truth interne)
    #   ANCRE-FAIBLE : leak-free MAIS >=1 arete sortante (hors SCC) atteignant
    #                  une cam leak-reachable — la boucle est amarree de
    #                  l'exterieur, mutualite tenue: WARNING, pas un fail.
    #                  (Lecon Delights<->Postcard: Postcard etait amarree via
    #                  Chase 2 A depuis le debut — pas une ile, un satellite.)
    #   PUR          : leak-free ET AUCUNE sortie ancree = vraie ile flottante,
    #                  derive collective possible -> FAIL CI.
    _memo = {}
    def _reaches_leak(c, _stack=()):
        if c in leaks:
            return True
        if c in _memo:
            return _memo[c]
        if c in _stack:
            return False
        r = any(_reaches_leak(b, _stack + (c,)) for b in adj.get(c, []))
        _memo[c] = r
        return r

    pure, tethered, healthy = [], [], []
    for comp in sccs:
        if any(c in leaks for c in comp):
            healthy.append(comp)
            continue
        cs = set(comp)
        out_anchored = any(b not in cs and _reaches_leak(b)
                           for c in comp for b in adj.get(c, []))
        (tethered if out_anchored else pure).append(comp)

    print(f"# SCC taille>={args.min_scc}: {len(sccs)}  "
          f"(PUR/ile={len(pure)}, ANCRE-FAIBLE={len(tethered)}, SAIN/leak-ancre={len(healthy)})")
    print()

    print("### CYCLES PURS (aucune leak dans la boucle - SUSPECT, ancrage externe requis)")
    if not pure:
        print("  (aucun)")
    for comp in pure:
        tiers = {c: lm_tiers.get(c) for c in comp}
        weakest = min(comp, key=lambda c: {'anchor': 0, 'high': 1, 'medium': 2,
                                           'low': 3, 'unverified': 4, None: 4}.get(lm_tiers.get(c), 4))
        print(f"\n  SCC ({len(comp)} cams): {comp}")
        print(f"    maillon faible (tier le plus bas): {weakest}")

    print("\n### CYCLES ANCRE-FAIBLE (leak-free mais amarres de l exterieur - WARNING)")
    if not tethered:
        print("  (aucun)")
    for comp in tethered:
        print(f"\n  SCC ({len(comp)} cams): {comp}")
        print(f"    mutualite tenue par ancrage externe — consolider via appuis propres (next_clicks)")

    print("\n### CYCLES SAINS (au moins une leak ancre la boucle)")
    if not healthy:
        print("  (aucun)")
    for comp in healthy:
        lk = [c for c in comp if c in leaks]
        print(f"\n  SCC ({len(comp)} cams): {comp}")
        print(f"    leak(s) d'ancrage: {lk}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
