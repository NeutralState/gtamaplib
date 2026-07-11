#!/usr/bin/env python3
# ANCHOR-CRITERION-V2 (2026-07-09): trois classes de SCC dans circular_deps.
#   SAIN         : leak DANS la boucle.
#   ANCRE-FAIBLE : leak-free MAIS >=1 arete sortante atteignant une cam
#                  leak-reachable -> WARNING (mutualite amarree de l'exterieur).
#   PUR          : leak-free ET aucune sortie ancree = vraie ile -> FAIL CI.
# LECON (saga Delights): la paire Delights<->Postcard n'a JAMAIS ete une ile —
# Postcard etait amarree via Chase (2) (A) depuis le debut. Le FAIL etait
# sur-severe; les clics restent la bonne CONSOLIDATION (sigma), pas un
# sauvetage. La contre-epreuve pre-clics a tue le critere naif — teste des
# DEUX bords avant livraison. Idempotent.
import sys
p = 'tools/audit/circular_deps.py'
src = open(p).read()
if 'ANCHOR-CRITERION-V2' in src:
    print('ok  deja patche'); sys.exit(0)

old = """    pure, healthy = [], []
    for comp in sccs:
        has_leak = any(c in leaks for c in comp)
        (healthy if has_leak else pure).append(comp)

    print(f"# SCC taille>={args.min_scc}: {len(sccs)}  "
          f"(PUR/auto-ref={len(pure)}, SAIN/leak-ancre={len(healthy)})")"""
new = """    # ANCHOR-CRITERION-V2 (2026-07-09): trois classes au lieu de deux.
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
          f"(PUR/ile={len(pure)}, ANCRE-FAIBLE={len(tethered)}, SAIN/leak-ancre={len(healthy)})")"""
assert old in src, 'ancre pure/healthy introuvable'
src = src.replace(old, new, 1)

old = '''        print(f"\\n  SCC ({len(comp)} cams): {comp}")
        print(f"    maillon faible (tier le plus bas): {weakest}")

    print("\\n### CYCLES SAINS (au moins une leak ancre la boucle)")'''
new = '''        print(f"\\n  SCC ({len(comp)} cams): {comp}")
        print(f"    maillon faible (tier le plus bas): {weakest}")

    print("\\n### CYCLES ANCRE-FAIBLE (leak-free mais amarres de l exterieur - WARNING)")
    if not tethered:
        print("  (aucun)")
    for comp in tethered:
        print(f"\\n  SCC ({len(comp)} cams): {comp}")
        print(f"    mutualite tenue par ancrage externe — consolider via appuis propres (next_clicks)")

    print("\\n### CYCLES SAINS (au moins une leak ancre la boucle)")'''
assert old in src, 'ancre section SAINS introuvable'
src = src.replace(old, new, 1)
open(p, 'w').write(src)
print('EDIT circular_deps: ANCHOR-CRITERION-V2')
