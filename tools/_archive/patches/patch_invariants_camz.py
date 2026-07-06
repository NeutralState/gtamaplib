"""Patch CAM-Z-V1 for tools/audit/invariants.py: no camera below
z=-1.0 (ground/water). Catches depth-degenerate solves that slide underground
while keeping perfect residuals. Whitelist for justified cases (Glitch (A)
out-of-bounds; Vice City 01 depth-degenerate pending low anchor; Jet Ski
load-bearing source of 14 fragile LMs — fix via bundle only, a solo re-solve
shattered them in a sandbox near-miss on 2026-07-02).

LESSON also encoded here: solver work MUST go through common.get_cam /
cam.get_pixel (the real gtamaplib model). A custom inline projection model
produced a pose off by 44 deg of yaw with an inverted roll (Gas Station
(Chase) (S), 2026-07-02) because of convention mismatch.

Idempotent. Backup: .bak_camz
"""
import shutil, sys
P = 'tools/audit/invariants.py'
s = open(P).read()
if 'CAM-Z-V1' in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_camz')
anchor = 'def main():'
assert anchor in s, 'anchor main introuvable'
s = s.replace(anchor, '# [CAM-Z-V1] No camera below ground/water. Catches depth-degenerate solves\n# that slide underground while keeping perfect residuals (Gas Station (Chase)\n# (S) was found at z=-34.7 on 2026-07-02).\nCAM_Z_MIN = -1.0\nCAM_Z_WHITELIST = {\n    # legit out-of-bounds glitch view (rough east-coast sketch)\n    \'Glitch (A)\': \'out-of-bounds glitch capture\',\n    # 4 obs = all high towers (Four Seasons x3 + WDNA 409m): depth-degenerate,\n    # sub-arcmin solutions span 2.4km. Pending a LOW anchor (the sign itself).\n    \'Vice City 01 (Vice City Sign)\': \'depth-degenerate, pending low anchor\',\n    # z=-2.34, mild — but load-bearing source of 14 km-fragile triangulations\n    # (Sunny Isles towers). Solo re-solve shatters them (near-miss 2026-07-02).\n    # Fix must go through the bundle (joint move), never solo.\n    \'Jet Ski\': \'load-bearing source of 14 fragile LMs; fix via bundle only\',\n}\n\ndef check_cam_z(fails):\n    for n, c in md.cameras.items():\n        xyz = c.get(\'xyz\')\n        if not xyz:\n            continue\n        if xyz[2] < CAM_Z_MIN and n not in CAM_Z_WHITELIST:\n            fails.append(f"CAM-Z: {n} at z={xyz[2]:.2f} (< {CAM_Z_MIN}) — "\n                         f"underground/underwater camera (depth-degenerate solve?)")\n\n\n' + anchor, 1)
old = 'fails = []'
assert old in s
s = s.replace(old, 'fails = []\n    check_cam_z(fails)  # [CAM-Z-V1]', 1)
open(P, 'w').write(s)
print('CAM-Z-V1 applique')
