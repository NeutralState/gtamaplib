"""Patch MULTISTART-V1 for tools/fit_minimal.py: coarse yaw x pitch grid
when the current pose sits on an inf plateau (marking behind the camera),
so Nelder-Mead gets a finite basin to descend. If NO finite basin exists on
the full grid, the tool now says so explicitly — which is itself a diagnosis:
no orientation can frame all markings from this xyz (wrong cam position or
wrong LM xyz). Idempotent.
"""
import sys
P = 'tools/fit_minimal.py'
s = open(P).read()
if 'MULTISTART-V1' in s:
    print('deja patche'); sys.exit(0)
old = """    x0 = [y0, p0, r0, f0] if solve_roll else [y0, p0, f0]
    best = minimize(loss, x0, method='Nelder-Mead',"""
assert old in s, 'anchor introuvable'
new = """    x0 = [y0, p0, r0, f0] if solve_roll else [y0, p0, f0]

""" + '    # [MULTISTART-V1] if the current pose projects a marking behind the cam\n    # (inf residual) or is wildly off, Nelder-Mead sits on a flat 1e9 plateau\n    # and never escapes. Coarse yaw x pitch grid to find a finite basin first.\n    if loss(x0) >= 1e9:\n        best_seed, best_val = None, 1e9\n        for yaw_g in range(0, 360, 15):\n            for pitch_g in (-30.0, -10.0, 0.0, 10.0):\n                seed = ([float(yaw_g), pitch_g, r0, f0] if solve_roll\n                        else [float(yaw_g), pitch_g, f0])\n                v = loss(seed)\n                if v < best_val:\n                    best_val, best_seed = v, seed\n        if best_seed is not None and best_val < 1e9:\n            print(f\'  [multi-start] plateau at current pose; best seed \'\n                  f\'yaw={best_seed[0]:.0f} pitch={best_seed[1]:.0f} \'\n                  f"({best_val:.1f}\')")\n            x0 = best_seed\n        else:\n            print(\'  [multi-start] no finite basin found on the coarse grid — \'\n                  \'the xyz is likely far off or a LM xyz is wrong.\')\n\n' + """    best = minimize(loss, x0, method='Nelder-Mead',"""
s = s.replace(old, new, 1)
open(P, 'w').write(s)
print('MULTISTART-V1 applique')
