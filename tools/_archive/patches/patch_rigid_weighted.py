#!/usr/bin/env python3
# RIGID-WEIGHTED-V1 (2026-07-13): corps rigides dans le BA pondere (celui des
# cycles — l'ancien rigid-body de bundle_adjust.py ne jouait plus). Methode:
# contraintes de DISTANCES INTERNES par paires vs la forme de reference (xyz
# au chargement) — preserve la forme a rotation/translation pres, additif pur
# (zero reparametrisation). Corps: four_seasons (8), portofino (3),
# vizcayne_north (3 coins sigma 1.4-1.9m). K_RIGID=3 (1m de deviation ~ 3
# unites residuelles, soft-rigid). Bench sandbox: cycle vert, mediane metres
# 0.193->0.187. 3 edits: defs+residus, N_RES, lignes sparsity. Idempotent.
import sys
p = 'tools/bundle_adjust_weighted.py'
src = open(p).read()
if 'RIGID-WEIGHTED-V1' in src:
    print('ok  deja patche'); sys.exit(0)
o = """def compute_residuals(p):
    \"\"\"Return flat residual vector: [obs residuals..., barrier residuals...]\"\"\"
    res = []"""
n = """# ── [RIGID-WEIGHTED-V1, 2026-07-13] Corps rigides dans le BA pondere ─────────
RIGID_BODY_DEFS = {
    'four_seasons': ['Four Seasons Hotel Miami (BE)', 'Four Seasons Hotel Miami (BW)',
                     'Four Seasons Hotel Miami (E)', 'Four Seasons Hotel Miami (NE)',
                     'Four Seasons Hotel Miami (NW)', 'Four Seasons Hotel Miami (SE)',
                     'Four Seasons Hotel Miami (SW)', 'Four Seasons Hotel Miami (W)'],
    'portofino': ['Portofino Tower (NW)', 'Portofino Tower (NE)', 'Portofino Tower (S)'],
    'vizcayne_north': ['Vizcayne North Condominium (NE)', 'Vizcayne North Condominium (SE)',
                       'Vizcayne North Condominium (NW)'],
}
K_RIGID = 3.0
_rigid_pairs = []
for _body, _names in RIGID_BODY_DEFS.items():
    _present = [x for x in _names if x in lm_idx and md.landmarks.get(x) is not None]
    for _i in range(len(_present)):
        for _j in range(_i + 1, len(_present)):
            _a, _b = _present[_i], _present[_j]
            _d = float(np.linalg.norm(np.asarray(md.landmarks[_a]) - np.asarray(md.landmarks[_b])))
            _rigid_pairs.append((_a, _b, _d))
    if _present:
        print(f"  [RIGID-WEIGHTED-V1] '{_body}': {len(_present)} LMs optimisables, forme figee")
if _rigid_pairs:
    print(f"  [RIGID-WEIGHTED-V1] {len(_rigid_pairs)} contraintes de distance (K={K_RIGID})")

def compute_residuals(p):
    \"\"\"Return flat residual vector: [obs residuals..., barrier residuals...]\"\"\"
    res = []"""
assert o in src, 'ancre compute_residuals'
src = src.replace(o, n, 1)
o = """            res.append(excess * stiff)

    return np.array(res)"""
n = """            res.append(excess * stiff)

    # [RIGID-WEIGHTED-V1] deviation de forme des corps rigides
    for _a, _b, _d in _rigid_pairs:
        _xa = np.asarray(get_lm_xyz(p, _a))
        _xb = np.asarray(get_lm_xyz(p, _b))
        res.append((float(np.linalg.norm(_xa - _xb)) - _d) * K_RIGID)

    return np.array(res)"""
assert o in src, 'ancre fin residus'
src = src.replace(o, n, 1)
o = "N_RES = N_OBS + N_BAR"
n = """N_RIGID = len(_rigid_pairs)   # [RIGID-WEIGHTED-V1]
N_RES = N_OBS + N_BAR + N_RIGID"""
assert o in src, 'ancre N_RES'
src = src.replace(o, n, 1)
o = """        sparsity[lm_bar_start + k, j:j+LM_PARAMS] = 1

sparsity = sparsity.tocsr()"""
n = """        sparsity[lm_bar_start + k, j:j+LM_PARAMS] = 1

# [RIGID-WEIGHTED-V1] sparsity des contraintes rigides (dernieres lignes)
for k, (_ra, _rb, _rd) in enumerate(_rigid_pairs):
    row = N_OBS + N_BAR + k
    for nm in (_ra, _rb):
        j = n_cam_params + lm_idx[nm] * LM_PARAMS
        sparsity[row, j:j+LM_PARAMS] = 1

sparsity = sparsity.tocsr()"""
assert o in src, 'ancre sparsity'
src = src.replace(o, n, 1)
open(p, 'w').write(src)
print('EDIT bundle_adjust_weighted.py: RIGID-WEIGHTED-V1 (4 edits)')
