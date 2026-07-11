#!/usr/bin/env python3
"""Patch triangulate_lm.py: respecter z_constraint (fixed) a l'ecriture, avec
residus recalcules au point snappe AVANT affichage (le dry valide exactement
la geometrie qui frappe le disque — meme semantique que md.update_landmark et
guarded_apply.snap_z). Lecons: Port (C) z=+7.03 (CI FAIL), Vake z=2.6e-4,
et error_m stockes mensongers (Port C: 6.56' libre vs 19.15' reel snappe).
Idempotent."""
import sys
p = 'tools/triangulate_lm.py'
src = open(p).read()
if 'z_constraint fixed:' in src:
    print('ok  deja patche')
    sys.exit(0)

anchor = """    if new_xyz is None:
        print(f"LM not updated, reason: {max_res}")
        return 1

    # Compute diff"""
block = """    if new_xyz is None:
        print(f"LM not updated, reason: {max_res}")
        return 1

    # z_constraint snap AVANT le calcul des residus/deltas affiches, pour que
    # le dry-run valide exactement la geometrie qui frappera le disque (meme
    # semantique que md.update_landmark et guarded_apply.snap_z; lecon
    # 2026-07-06/07: Port (C) z=+7.03 et Vake Island z=2.6e-4 = CI FAIL).
    zc = (lm.get('z_constraint') or None)
    if zc and zc.get('type') == 'fixed':
        z_target = float(zc['value'])
        if new_xyz[2] != z_target:
            print(f"z_constraint fixed: z {new_xyz[2]:.4f} -> {z_target} (snap)")
            new_xyz = [new_xyz[0], new_xyz[1], z_target]
            rays = _build_rays(kept, args.lm_name, pixels)
            snapped_res = _residuals_arcmin(new_xyz, rays)
            if snapped_res:
                max_res = max(snapped_res.values())
                print(f"  residus recalcules au point snappe: max {max_res:.3f}'")

    # Compute diff"""
assert anchor in src, 'ancre introuvable — triangulate_lm.py a change'
src = src.replace(anchor, block, 1)
open(p, 'w').write(src)
print('triangulate_lm.py patche (z_constraint snap + residus honnetes)')
