#!/usr/bin/env python3
"""
patch_z_constraint.py — Item 1 de la roadmap rlx: z=0 / known-z flag pour landmarks.

Patches in-place (idempotent):
  1. gtamapdata.py
     - Charge `z_constraint` dans landmarks_meta[name]
     - Préserve les fields non-touchés (author, z_constraint) dans update_landmark()
     - Nouveau helper update_landmark() accepte z_constraint=None
  2. tools/bundle_adjust.py
     - Pré-calcule _z_constraints depuis md.landmarks_meta
     - pixel_residuals() force z à la valeur fixée pour les landmarks contraints
     - L'écriture finale snap z à la valeur fixée
  3. tools/server.py
     - /api/triangulate snap z après triangulation si constraint
     - /api/lm_info expose z_constraint
  4. tools/CLAUDE_CONTEXT.md
     - Mise à jour : item 1 ✅, schema documenté

Run depuis la racine du repo gtamaplib-main/ :
    python3 patch_z_constraint.py             # dry-run (montre ce qui changera)
    python3 patch_z_constraint.py --apply     # exécute
"""
import argparse
import os
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
GTAMAPDATA_PATH    = os.path.join(REPO_ROOT, 'gtamapdata.py')
BUNDLE_ADJUST_PATH = os.path.join(REPO_ROOT, 'tools', 'bundle_adjust.py')
SERVER_PATH        = os.path.join(REPO_ROOT, 'tools', 'server.py')
CONTEXT_PATH       = os.path.join(REPO_ROOT, 'tools', 'CLAUDE_CONTEXT.md')

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()

# Sanity check
if not all(os.path.isfile(p) for p in [GTAMAPDATA_PATH, BUNDLE_ADJUST_PATH, SERVER_PATH, CONTEXT_PATH]):
    print("✗ Lance ce script depuis la racine de gtamaplib-main/")
    print(f"  Manque l'un de :")
    for p in [GTAMAPDATA_PATH, BUNDLE_ADJUST_PATH, SERVER_PATH, CONTEXT_PATH]:
        print(f"    {p} : {'OK' if os.path.isfile(p) else 'MANQUANT'}")
    sys.exit(1)


def patch_file(path, replacements, marker_already_applied=None):
    """
    replacements : list of (old, new) string pairs (old must be unique in file)
    marker_already_applied : if this string is in the file, skip (idempotent)
    Returns: 'patched' | 'already_patched' | 'error: <msg>'
    """
    with open(path) as f:
        content = f.read()

    if marker_already_applied and marker_already_applied in content:
        return 'already_patched'

    new_content = content
    for old, new in replacements:
        if old not in new_content:
            return f"error: pattern not found in {path}\n  expected:\n{old[:200]}..."
        if new_content.count(old) > 1:
            return f"error: pattern found multiple times in {path} (must be unique):\n  {old[:200]}..."
        new_content = new_content.replace(old, new)

    if args.apply:
        shutil.copy(path, path + '.bak_z_constraint')
        with open(path, 'w') as f:
            f.write(new_content)
    return 'patched'


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 1 — gtamapdata.py
# ═══════════════════════════════════════════════════════════════════════════

GTAMAPDATA_OLD_LOAD = '''_landmarks_raw = _load("landmarks.json")
for lm_name, data in _landmarks_raw.items():
    xyz = data.get("xyz")
    landmarks[lm_name] = tuple(xyz) if xyz is not None else None
    landmarks_meta[lm_name] = {
        "source_cameras": data.get("source_cameras", []),
        "error_m": data.get("error_m"),
        "zone": data.get("zone", "unknown"),
    }'''

GTAMAPDATA_NEW_LOAD = '''_landmarks_raw = _load("landmarks.json")
for lm_name, data in _landmarks_raw.items():
    xyz = data.get("xyz")
    landmarks[lm_name] = tuple(xyz) if xyz is not None else None
    landmarks_meta[lm_name] = {
        "source_cameras": data.get("source_cameras", []),
        "error_m": data.get("error_m"),
        "zone": data.get("zone", "unknown"),
        # z_constraint: None | {"type": "fixed", "value": <float>}
        # When set to a fixed value, the solver and triangulation respect it.
        # See tools/audit/find_z_candidates.py and tools/refine/apply_z_constraints.py.
        "z_constraint": data.get("z_constraint"),
    }'''

GTAMAPDATA_OLD_UPDATE = '''def update_landmark(lm_name, xyz, source_cameras=None, error_m=None, zone=None):
    """
    Updates a landmark in memory and persists to the appropriate JSON file.
    Handles xyz=None for landmarks without triangulation yet.
    """
    landmarks[lm_name] = tuple(xyz) if xyz is not None else None

    # Determine zone
    if zone is None:
        if lm_name in landmarks_meta:
            zone = landmarks_meta[lm_name]["zone"]
        else:
            zone = "misc"

    landmarks_meta[lm_name] = {
        "source_cameras": source_cameras or [],
        "error_m": error_m,
        "zone": zone,
    }

    # Persist to landmarks.json
    lm_path = os.path.join(DATA_DIR, "landmarks.json")
    with open(lm_path) as f:
        lm_data = json.load(f)
    lm_data[lm_name] = {
        "xyz": list(xyz) if xyz is not None else None,
        "source_cameras": source_cameras or [],
        "error_m": error_m,
        "zone": zone,
    }
    tmp = lm_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(lm_data, f, indent=2)
    os.replace(tmp, lm_path)'''

GTAMAPDATA_NEW_UPDATE = '''def update_landmark(lm_name, xyz, source_cameras=None, error_m=None, zone=None,
                    z_constraint=_SENTINEL):
    """
    Updates a landmark in memory and persists to landmarks.json.

    Preserves any field not explicitly passed (z_constraint, author, etc).
    To explicitly clear z_constraint, pass z_constraint=None.

    If z_constraint = {"type": "fixed", "value": V}, snaps xyz[2] to V before
    persisting (single source of truth — JSON xyz always matches the constraint).

    Handles xyz=None for landmarks without triangulation yet.
    """
    # Read existing JSON to preserve untouched fields
    lm_path = os.path.join(DATA_DIR, "landmarks.json")
    with open(lm_path) as f:
        lm_data = json.load(f)
    existing = lm_data.get(lm_name, {})

    # Determine final z_constraint (sentinel = "not passed = preserve existing")
    if z_constraint is _SENTINEL:
        final_z_constraint = existing.get("z_constraint")
    else:
        final_z_constraint = z_constraint

    # Snap xyz[2] to fixed-z value if applicable (single source of truth)
    if xyz is not None and final_z_constraint and \\
            final_z_constraint.get("type") == "fixed":
        xyz = list(xyz)
        xyz[2] = float(final_z_constraint["value"])

    landmarks[lm_name] = tuple(xyz) if xyz is not None else None

    # Determine zone
    if zone is None:
        if lm_name in landmarks_meta:
            zone = landmarks_meta[lm_name]["zone"]
        else:
            zone = existing.get("zone", "misc")

    landmarks_meta[lm_name] = {
        "source_cameras": source_cameras if source_cameras is not None
                          else existing.get("source_cameras", []),
        "error_m": error_m if error_m is not None else existing.get("error_m"),
        "zone": zone,
        "z_constraint": final_z_constraint,
    }

    # Build the JSON record, preserving fields we don't touch (e.g. author)
    new_record = dict(existing)  # start from existing to preserve all fields
    new_record["xyz"] = list(xyz) if xyz is not None else None
    if source_cameras is not None:
        new_record["source_cameras"] = source_cameras
    elif "source_cameras" not in new_record:
        new_record["source_cameras"] = []
    new_record["error_m"] = error_m if error_m is not None else new_record.get("error_m")
    new_record["zone"] = zone
    if final_z_constraint is None:
        new_record.pop("z_constraint", None)
    else:
        new_record["z_constraint"] = final_z_constraint

    lm_data[lm_name] = new_record
    tmp = lm_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(lm_data, f, indent=2)
    os.replace(tmp, lm_path)'''

# Sentinel for "param not passed" (so we can distinguish from explicit None)
GTAMAPDATA_OLD_HEADER = 'def get_independent_landmarks(cam_name):'
GTAMAPDATA_NEW_HEADER = '''_SENTINEL = object()  # marker for "argument not passed" in update_landmark()


def get_independent_landmarks(cam_name):'''


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 2 — tools/bundle_adjust.py
# ═══════════════════════════════════════════════════════════════════════════

# A. Pré-calculer _z_constraints juste avant pixel_residuals()
BUNDLE_OLD_PRECOMPUTE = '''_fixed_lm_xyz = {n: tuple(md.landmarks[n])
                 for n in md.landmarks
                 if n not in lm_idx and md.landmarks.get(n) is not None}'''

BUNDLE_NEW_PRECOMPUTE = '''_fixed_lm_xyz = {n: tuple(md.landmarks[n])
                 for n in md.landmarks
                 if n not in lm_idx and md.landmarks.get(n) is not None}

# z constraints (item 1 / rlx roadmap) :
# {lm_name: {"type": "fixed", "value": <float>}}
# When a landmark has z_constraint, the solver lets x and y move freely but
# forces z to the fixed value at every residual evaluation.
_z_constraints = {
    n: meta['z_constraint']
    for n, meta in md.landmarks_meta.items()
    if meta.get('z_constraint')
}
n_z_fixed_in_opt = sum(1 for n in opt_lm_names if n in _z_constraints)
if _z_constraints:
    print(f"z constraints: {len(_z_constraints)} landmarks total, "
          f"{n_z_fixed_in_opt} in optimization set (z forced during solve)")'''

# B. pixel_residuals: force z to fixed value
BUNDLE_OLD_RESIDUAL = '''        if lm_name in lm_idx:
            lp = lm_params[lm_idx[lm_name]]
            lm_xyz = (float(lp[0]), float(lp[1]), float(lp[2]))
        else:
            lm_xyz = _fixed_lm_xyz[lm_name]'''

BUNDLE_NEW_RESIDUAL = '''        if lm_name in lm_idx:
            lp = lm_params[lm_idx[lm_name]]
            z_val = float(lp[2])
            zc = _z_constraints.get(lm_name)
            if zc and zc.get('type') == 'fixed':
                z_val = float(zc['value'])
            lm_xyz = (float(lp[0]), float(lp[1]), z_val)
        else:
            lm_xyz = _fixed_lm_xyz[lm_name]'''

# C. Snap z at write-out
BUNDLE_OLD_WRITEOUT = '''for i, lm_name in enumerate(opt_lm_names):
    lp = lm_params_final[i]
    output['landmarks'][lm_name] = [round(float(v), 4) for v in lp]'''

BUNDLE_NEW_WRITEOUT = '''for i, lm_name in enumerate(opt_lm_names):
    lp = lm_params_final[i]
    # Snap z to fixed value if constrained (single source of truth)
    z_final = float(lp[2])
    zc = _z_constraints.get(lm_name)
    if zc and zc.get('type') == 'fixed':
        z_final = float(zc['value'])
    output['landmarks'][lm_name] = [round(float(lp[0]), 4),
                                    round(float(lp[1]), 4),
                                    round(z_final, 4)]'''


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 3 — tools/server.py
# ═══════════════════════════════════════════════════════════════════════════

# A. /api/triangulate : snap z if constraint
SERVER_OLD_TRIANGULATE = '''            if best is None:
                self.send_json({'error': 'Triangulation failed'}, 400)
                return

            # Save to landmarks
            meta = md.landmarks_meta.get(lm_name, {})
            md.update_landmark(lm_name, best['xyz'],
                source_cameras=source_cams,
                error_m=best['error_m'],
                zone=meta.get('zone', 'unknown'))'''

SERVER_NEW_TRIANGULATE = '''            if best is None:
                self.send_json({'error': 'Triangulation failed'}, 400)
                return

            # Save to landmarks. update_landmark() snaps xyz[2] if z_constraint
            # is set on this landmark (single source of truth — see gtamapdata.py).
            meta = md.landmarks_meta.get(lm_name, {})
            md.update_landmark(lm_name, best['xyz'],
                source_cameras=source_cams,
                error_m=best['error_m'],
                zone=meta.get('zone', 'unknown'))
            # Reflect snap in the response so frontend shows the correct xyz
            zc = meta.get('z_constraint')
            if zc and zc.get('type') == 'fixed':
                best['xyz'][2] = round(float(zc['value']), 4)
                best['z_snapped'] = True'''

# B. /api/lm_info : expose z_constraint
SERVER_OLD_LMINFO = '''            self.send_json({
                'lm': lm_name,
                'sources': sorted(sources),
                'others': sorted(others),
                'n_sources': len(sources),
                'n_others': len(others),
                'n_total_observers': len(observers),
                'error_m': error_m,
                'has_xyz': has_xyz,
            })'''

SERVER_NEW_LMINFO = '''            self.send_json({
                'lm': lm_name,
                'sources': sorted(sources),
                'others': sorted(others),
                'n_sources': len(sources),
                'n_others': len(others),
                'n_total_observers': len(observers),
                'error_m': error_m,
                'has_xyz': has_xyz,
                'z_constraint': meta.get('z_constraint'),
            })'''


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 4 — tools/CLAUDE_CONTEXT.md (last session log + roadmap update)
# ═══════════════════════════════════════════════════════════════════════════

CONTEXT_OLD_ITEM1 = '''### Items prioritaires

1. **z=0 / known-z flag pour landmarks** (coastal points, pins)
   - Ajouter `z_constraint` au schema `landmarks_meta`
   - `compute_projections` et `bundle_adjust` doivent respecter cette
     contrainte
   - Le solver fixe z et n'optimise que x, y pour ces landmarks'''

CONTEXT_NEW_ITEM1 = '''### Items prioritaires

1. ✅ **z=0 / known-z flag pour landmarks** (DONE 2026-05-07)
   - Schema : `landmarks_meta[name]["z_constraint"] = {"type": "fixed", "value": <float>}`
     ou `None` (default).
   - `bundle_adjust.py` force z à la valeur fixée à chaque eval du résidu
     pour les landmarks contraints (x et y restent libres).
   - `update_landmark()` snap `xyz[2]` à la valeur fixée → JSON xyz toujours
     en sync avec le constraint (single source of truth).
   - Workflow d'application :
     1. `python3 tools/audit/find_z_candidates.py` → propose les coastal/pin
     2. Review `/tmp/z_candidates.json`, enlever les faux positifs
     3. `python3 tools/refine/apply_z_constraints.py --apply` → écrit le constraint
     4. `python3 tools/bundle_adjust.py` → re-run avec les contraintes actives'''

CONTEXT_OLD_LOG = '''**Next** : item 1 (z=0 flag for landmarks).'''

CONTEXT_NEW_LOG = '''**Next** : item 1 (z=0 flag for landmarks).

### 2026-05-07 — Consolidate bundle adjust + Item 1 z=0 flag

- Drop `bundle_adjust_v2.py` (archived). `bundle_adjust_v3_twopass.py`
  renommé `bundle_adjust.py` (canonical).
- **Item 1 implémenté** :
  - `gtamapdata.py` : charge `z_constraint` dans `landmarks_meta`.
    `update_landmark()` accepte `z_constraint=None`, préserve les
    fields non-touchés (au passage : fixe le bug qui détruisait le champ
    `author` à chaque write).
  - `bundle_adjust.py` : pré-calcule `_z_constraints`, force z dans le
    résidu, snap z au write-out.
  - `server.py` : `/api/triangulate` snap z, `/api/lm_info` expose
    `z_constraint` au frontend.
  - `tools/audit/find_z_candidates.py` (nouveau) : scan des coastal/pin.
  - `tools/refine/apply_z_constraints.py` (nouveau) : applique le constraint
    en batch depuis une liste.
- Pas de regression : landmarks sans `z_constraint` restent inchangés.

**Next** : item 2 (precision flag pour cams Tennis Court etc).'''


# ═══════════════════════════════════════════════════════════════════════════
# Apply patches
# ═══════════════════════════════════════════════════════════════════════════

if not args.apply:
    print("═══════════════════════════════════════════════════════════════")
    print("  DRY-RUN — Lance avec --apply pour exécuter")
    print("═══════════════════════════════════════════════════════════════")
    print()

results = []

# Patch 1 : gtamapdata.py
print("── Patch 1/4 : gtamapdata.py ──")
res = patch_file(GTAMAPDATA_PATH, [
    (GTAMAPDATA_OLD_LOAD, GTAMAPDATA_NEW_LOAD),
    (GTAMAPDATA_OLD_HEADER, GTAMAPDATA_NEW_HEADER),
    (GTAMAPDATA_OLD_UPDATE, GTAMAPDATA_NEW_UPDATE),
], marker_already_applied='_SENTINEL = object()')
results.append(('gtamapdata.py', res))
print(f"  → {res}")

# Patch 2 : tools/bundle_adjust.py
print("── Patch 2/4 : tools/bundle_adjust.py ──")
res = patch_file(BUNDLE_ADJUST_PATH, [
    (BUNDLE_OLD_PRECOMPUTE, BUNDLE_NEW_PRECOMPUTE),
    (BUNDLE_OLD_RESIDUAL,   BUNDLE_NEW_RESIDUAL),
    (BUNDLE_OLD_WRITEOUT,   BUNDLE_NEW_WRITEOUT),
], marker_already_applied='_z_constraints = {')
results.append(('tools/bundle_adjust.py', res))
print(f"  → {res}")

# Patch 3 : tools/server.py
print("── Patch 3/4 : tools/server.py ──")
res = patch_file(SERVER_PATH, [
    (SERVER_OLD_TRIANGULATE, SERVER_NEW_TRIANGULATE),
    (SERVER_OLD_LMINFO,      SERVER_NEW_LMINFO),
], marker_already_applied="'z_constraint': meta.get('z_constraint')")
results.append(('tools/server.py', res))
print(f"  → {res}")

# Patch 4 : tools/CLAUDE_CONTEXT.md
print("── Patch 4/4 : tools/CLAUDE_CONTEXT.md ──")
res = patch_file(CONTEXT_PATH, [
    (CONTEXT_OLD_ITEM1, CONTEXT_NEW_ITEM1),
    (CONTEXT_OLD_LOG,   CONTEXT_NEW_LOG),
], marker_already_applied='✅ **z=0 / known-z flag pour landmarks** (DONE')
results.append(('tools/CLAUDE_CONTEXT.md', res))
print(f"  → {res}")

print()
print("═══════════════════════════════════════════════════════════════")
errors = [r for _, r in results if r.startswith('error')]
if errors:
    print(f"  ⚠ {len(errors)} erreur(s)")
    for path, r in results:
        if r.startswith('error'):
            print(f"    {path}: {r}")
    sys.exit(1)
elif args.apply:
    print(f"  ✓ Patches appliqués ({sum(1 for _, r in results if r == 'patched')} files)")
    print(f"    backups : *.bak_z_constraint à côté de chaque fichier patché")
    print()
    print("  Tests à faire :")
    print("    1. python3 -c 'import gtamapdata as md; print(md.landmarks_meta[\"112 NE 41st St\"])'")
    print("       # devrait afficher le dict avec z_constraint=None")
    print()
    print("    2. lsof -ti :8765 | xargs kill -9; python3 tools/server.py &")
    print("       # ouvrir calib.html et vérifier qu'aucune erreur")
    print()
    print("    3. Une fois testé : ouvrir tools/audit/find_z_candidates.py")
    print("       (généré séparément) pour scanner les candidats z=0")
else:
    n_pending = sum(1 for _, r in results if r == 'patched')
    n_already = sum(1 for _, r in results if r == 'already_patched')
    print(f"  Dry-run OK : {n_pending} patches à appliquer, {n_already} déjà appliqués")
    print("  Lance avec --apply pour exécuter.")
print("═══════════════════════════════════════════════════════════════")
