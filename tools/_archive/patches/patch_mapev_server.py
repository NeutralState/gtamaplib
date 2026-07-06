"""Patch serveur MAP-EVIDENCE-V1: preuve map dans l'inspecteur de LM.

- /api/triangulate?dry=1 : proposition de retriangulation SANS ecrire
- /api/lm_map_crop?lm=&x2=&y2= : crop yanis, crosshair cyan (actuel) +
  orange optionnel (propose)
- /api/map_verdict?lm=&status= : lire/ecrire map_validated.json

PREREQUIS: tools/map_validate.py present (importe pour crop_at/verdicts),
patch triage applique (ancre /api/triage). Idempotent. Backup: .bak_mapev
"""
import shutil, sys

P = 'tools/server.py'
s = open(P).read()
if 'MAP-EVIDENCE-V1' in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_mapev')

old = '            # is set on this landmark (single source of truth — see gtamapdata.py).\n            meta = md.landmarks_meta.get(lm_name, {})'
assert old in s, 'anchor triangulate introuvable'
s = s.replace(old, "            # [MAP-EVIDENCE-V1] dry=1: retourner la proposition sans ecrire\n            if qs.get('dry', [''])[0] == '1':\n                best['dry'] = True\n                self.send_json(best)\n                return\n" + old, 1)

anchor = "        elif path == '/api/triage':"
assert anchor in s, 'anchor /api/triage introuvable (patch triage requis)'
s = s.replace(anchor, "        elif path == '/api/lm_map_crop':\n            # [MAP-EVIDENCE-V1] crop yanis V13 centre sur le LM. Crosshair cyan\n            # = xyz actuel; crosshair orange optionnel (x2,y2) = position proposee.\n            lm_name = unquote(qs.get('lm', [''])[0])\n            xyz = md.landmarks.get(lm_name)\n            if xyz is None:\n                self.send_json({'error': 'LM sans xyz'}, 404); return\n            import sys as _sys, io as _io2, math as _m2\n            if TOOL_DIR not in _sys.path: _sys.path.insert(0, TOOL_DIR)\n            from map_validate import crop_at, MPPX\n            from PIL import ImageDraw as _ImageDraw\n            wx, wy = xyz[0], xyz[1]\n            x2 = qs.get('x2', [None])[0]; y2 = qs.get('y2', [None])[0]\n            half = 80.0\n            cx, cy = wx, wy\n            if x2 is not None and y2 is not None:\n                x2, y2 = float(x2), float(y2)\n                cx, cy = (wx + x2) / 2, (wy + y2) / 2\n                half = max(80.0, _m2.hypot(x2 - wx, y2 - wy) / 2 + 50)\n            img = crop_at(cx, cy, half)\n            if img is None:\n                self.send_json({'error': 'hors map / tuiles indisponibles'}, 404); return\n            d = _ImageDraw.Draw(img)\n            def _cross(wxp, wyp, col):\n                px = img.width / 2 + (wxp - cx) / MPPX\n                py = img.height / 2 - (wyp - cy) / MPPX\n                g, L = 10, 26\n                for seg in [((px-L,py),(px-g,py)),((px+g,py),(px+L,py)),((px,py-L),(px,py-g)),((px,py+g),(px,py+L))]:\n                    d.line(seg, fill=col, width=2)\n            # crop_at dessine deja le crosshair CENTRE; si x2 present le centre\n            # est le midpoint -> redessiner les deux points explicitement\n            if x2 is not None:\n                _cross(wx, wy, (0, 230, 255))\n                _cross(x2, y2, (245, 158, 11))\n            sz = 300\n            img = img.resize((sz, sz))\n            buf = _io2.BytesIO(); img.save(buf, 'JPEG', quality=82)\n            data = buf.getvalue()\n            self.send_response(200)\n            self.send_header('Content-Type', 'image/jpeg')\n            self.send_header('Cache-Control', 'no-store')\n            self.send_header('Content-Length', str(len(data)))\n            self.end_headers(); self.wfile.write(data)\n\n        elif path == '/api/map_verdict':\n            # [MAP-EVIDENCE-V1] lire/ecrire le verdict de preuve map d'un LM\n            lm_name = unquote(qs.get('lm', [''])[0])\n            status = qs.get('status', [''])[0]\n            import sys as _sys\n            if TOOL_DIR not in _sys.path: _sys.path.insert(0, TOOL_DIR)\n            from map_validate import load_validated, save_validated\n            cur = load_validated()\n            if status in ('validated', 'rejected'):\n                from datetime import date as _date\n                cur[lm_name] = {'status': status, 'date': _date.today().isoformat()}\n                save_validated(cur)\n            elif status == 'clear':\n                cur.pop(lm_name, None)\n                save_validated(cur)\n            self.send_json({'lm': lm_name, 'verdict': (cur.get(lm_name) or {}).get('status')})\n\n" + anchor, 1)
open(P, 'w').write(s)
print('serveur MAP-EVIDENCE-V1 patche. Backup: .bak_mapev')
