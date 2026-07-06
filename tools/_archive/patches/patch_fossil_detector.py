"""patch_fossil_detector.py — FOSSIL-SCAN-V1 (2026-07-03).

A "fossil" is a LM whose OWN source cameras now reject it: stale xyz from an
old pose of the source. Caught by hand 3x this week (Easy Hill, Diner Bays,
WDNA mast). This wires automatic detection into:
  - tools/common.py: find_fossils() shared scanner
  - tools/ci_healthcheck.py: warning section on every push (never fails CI)
  - tools/server.py: /api/triage payload gains 'fossils'
  - tools/calib.html: FOSSILS section in the Triage board + one-click quarantine
First run on 2026-07-03 state: 27 fossils, incl. 6x Beach (A-F) no-proj and
New Foundation Church (child of the Chase (2)(A) refine we never cascaded).
Idempotent. Backups: .bak_fossil
"""
import shutil, sys

def guard(path):
    s = open(path).read()
    if 'FOSSIL-SCAN-V1' in s:
        print(f'{path}: deja patche'); return None
    shutil.copy(path, path + '.bak_fossil')
    return s

s = guard('tools/common.py')
if s is not None:
    open('tools/common.py', 'w').write(s + '\n\n# [FOSSIL-SCAN-V1] A "fossil" is a landmark whose OWN source cameras now\n# reject it: its xyz was triangulated/derived from an old pose of a source\n# cam, the cam got refined since, the LM stayed frozen. Pattern caught 3x by\n# hand during 2026-07 (Easy Hill, the Diner Bays, the WDNA mast sub-points).\nFOSSIL_THRESHOLD_ARCMIN = 15.0\n\ndef find_fossils(threshold=FOSSIL_THRESHOLD_ARCMIN):\n    """Scan all triangulated LMs; return [{lm, source, resid, n_sources}]\n    for every LM where a source cam that still marks it disagrees by more\n    than threshold arcmin. Blind spot: a fossil whose source no longer has\n    a marking is undetectable (no ray to compare)."""\n    import math as _math\n    out = []\n    for lm, xyz in md.landmarks.items():\n        if xyz is None:\n            continue\n        srcs = (md.landmarks_meta.get(lm) or {}).get(\'source_cameras\', []) or []\n        worst = None\n        n_checked = 0\n        for cn in srcs:\n            if cn not in md.cameras or not md.cameras[cn].get(\'xyz\'):\n                continue\n            px = md.pixels.get(cn, {}).get(lm)\n            if px is None or is_excluded_marking(cn, lm):\n                continue\n            cam = get_cam(cn)\n            p = cam.get_pixel(xyz)\n            if p is None:\n                r = float(\'inf\')\n            else:\n                dx = (p[0] - px[0]) * cam.hfov / cam.w * 60\n                dy = (p[1] - px[1]) * cam.vfov / cam.h * 60\n                r = _math.hypot(dx, dy)\n            n_checked += 1\n            if worst is None or r > worst[0]:\n                worst = (r, cn)\n        if worst is not None and worst[0] > threshold:\n            out.append({\'lm\': lm, \'source\': worst[1],\n                        \'resid\': None if worst[0] == float(\'inf\') else round(worst[0], 1),\n                        \'n_sources\': len(srcs), \'n_checked\': n_checked})\n    out.sort(key=lambda x: -(x[\'resid\'] if x[\'resid\'] is not None else 1e9))\n    return out\n')
    print('tools/common.py: find_fossils() ajoute')

s = guard('tools/ci_healthcheck.py')
if s is not None:
    old = "    if not any(f_.startswith('JSON') for f_ in fails):\n        print('✓ json hygiene OK')"
    assert old in s, 'anchor ci'
    s = s.replace(old, old + '\n\n    # ── 6. fossil scan (WARNING only, never fails) [FOSSIL-SCAN-V1] ─────\n    # LMs whose own source cams reject them = stale xyz from an old pose.\n    try:\n        from common import find_fossils\n        fossils = find_fossils()\n        if fossils:\n            print(f\'⚠ fossils: {len(fossils)} LM(s) rejected by their own source\')\n            for x in fossils[:5]:\n                r = f"{x[\'resid\']}\'" if x[\'resid\'] is not None else \'no-proj\'\n                print(f"    {r:>9s}  {x[\'lm\']}  (source: {x[\'source\']})")\n            if len(fossils) > 5:\n                print(f\'    ... +{len(fossils)-5} more (see Triage board)\')\n        else:\n            print(\'✓ fossils: none\')\n    except Exception as e:\n        print(f\'⚠ fossil scan failed: {e}\')', 1)
    open('tools/ci_healthcheck.py', 'w').write(s)
    print('tools/ci_healthcheck.py: section fossiles (warning)')

s = guard('tools/server.py')
if s is not None:
    old = "            self.send_json({'rows': rows, 'n': len(rows)})"
    assert old in s, 'anchor server'
    new = """            # [FOSSIL-SCAN-V1] LMs rejected by their own source cams
            try:
                from common import find_fossils
                _fossils = find_fossils()
            except Exception:
                _fossils = []
            self.send_json({'rows': rows, 'n': len(rows), 'fossils': _fossils})"""
    s = s.replace(old, new, 1)
    open('tools/server.py', 'w').write(s)
    print('tools/server.py: /api/triage expose fossils')

s = guard('tools/calib.html')
if s is not None:
    s = s.replace('<div id="triage-rows">chargement…</div>', '<div id="triage-rows">loading…</div>', 1)
    CALIB_BLOCK = '    // [FOSSIL-SCAN-V1] LMs rejected by their own source cams (stale xyz\n    // from an old pose of the source). One-click quarantine.\n    if (d.fossils && d.fossils.length) {\n      const h = document.createElement(\'div\');\n      h.style.cssText = \'margin:16px 0 4px;font-weight:700;color:#f97316\';\n      h.textContent = \'FOSSILS — LM rejected by its own source (\' + d.fossils.length + \')\';\n      box.appendChild(h);\n      const note = document.createElement(\'div\');\n      note.style.cssText = \'color:var(--mid,#888);margin:0 0 6px;font-size:11px\';\n      note.textContent = \'Stale xyz from an old source pose. Quarantine, or re-mark + retriangulate from the current pose.\';\n      box.appendChild(note);\n      for (const f of d.fossils) {\n        const row = document.createElement(\'div\');\n        row.style.cssText = \'display:flex;gap:10px;align-items:center;padding:5px 6px;border-radius:5px;border-bottom:1px solid #ffffff0e\';\n        const r = f.resid !== null ? f.resid + "\'" : \'no-proj\';\n        row.innerHTML = \'<span style="color:var(--text,#ddd);min-width:220px">\' + f.lm + \'</span>\' +\n          \'<span style="color:#f97316;min-width:62px">\' + r + \'</span>\' +\n          \'<span style="flex:1;color:var(--mid,#999)">source: \' + f.source + \' · \' + f.n_sources + \' src</span>\';\n        const act = document.createElement(\'button\');\n        act.style.cssText = \'background:#ffffff14;border:1px solid var(--border,#333);color:var(--text,#ddd);\' +\n                            \'border-radius:5px;padding:3px 9px;cursor:pointer;white-space:nowrap\';\n        act.textContent = \'quarantine LM\';\n        act.addEventListener(\'click\', async () => {\n          if (!confirm(\'Quarantine (null xyz) "\' + f.lm + \'"? Markings remain in pixels.json.\')) return;\n          const res = await fetch(\'/api/quarantine_lm?lm=\' + encodeURIComponent(f.lm)).then(x => x.json());\n          if (res.ok) load(); else alert(res.error || \'error\');\n        });\n        row.appendChild(act);\n        box.appendChild(row);\n      }\n    }\n  }\n\n'
    old = '      box.appendChild(row);\n    }\n  }\n\n  function selectCamByName(name) {'
    assert old in s, 'anchor calib'
    s = s.replace(old, "      box.appendChild(row);\n    }\n\n" + CALIB_BLOCK + "  function selectCamByName(name) {", 1)
    open('tools/calib.html', 'w').write(s)
    print('tools/calib.html: section FOSSILS dans le Triage board')

print('FOSSIL-SCAN-V1 complet. Redemarre le serveur + hard refresh.')
