#!/usr/bin/env python3
# ASSIST-SMART-V1 (2026-07-10): l'Assist arrete de montrer des ghosts
# impossibles. Deux filtres cote serveur (assist seulement, &smart=0 pour
# debrayer):
#  1) SUB-RESOLUTION: un feature dont le contexte ~6m tombe sous 2px a cette
#     distance/focale n'est pas identifiable -> masque (les Light Pollution
#     a 12-16km disparaissent d'eux-memes).
#  2) OCCLUSION PAIRWISE: deux LM projetes a <18px l'un de l'autre et le
#     lointain >35% plus loin -> le proche le cache probablement -> masque.
#     Proxy points-seulement: pas de mesh de la ville (la map EST le produit).
# CALIBRATION VECUE: v1 en angle (0.5 deg) masquait 282/296 sur la Postcard
# (30px a cette focale = buildings cote a cote declares caches) -> pixel-space.
# Valide: Postcard 191 masques (mediane 9km, sub-res legitime + dedoublonnage
# meme-building), JD05 teleobjectif 0 masque, cams normales ~18%.
# UI: footer du panneau assist = compte des masques + toggle clic.
# Idempotent.
import sys

p = 'tools/server.py'
src = open(p).read()
if 'ASSIST-SMART-V1' in src:
    print(f'ok  {p}: deja patche')
else:
    o = """            assist = qs.get('mode', [''])[0] == 'assist'"""
    n = """            assist = qs.get('mode', [''])[0] == 'assist'
            # [ASSIST-SMART-V1] filtres intelligents (assist seulement,
            # debrayables par &smart=0): sub-resolution + occlusion pairwise.
            smart = assist and qs.get('smart', ['1'])[0] != '0'
            _smart_hidden = 0
            _f_px = None
            try:
                _hfov = md.cameras[cam_name].get('fov', [None])[0]
                if _hfov:
                    _f_px = (target_w / 2.0) / math.tan(math.radians(_hfov / 2.0))
            except Exception:
                pass"""
    assert o in src, 'ancre s1 (assist=)'
    src = src.replace(o, n, 1)
    o = """                    _entry = {
                        'name': lm_name,
                        'type': 'point',
                        'pixel': [x, y],
                    }"""
    n = """                    _entry = {
                        'name': lm_name,
                        'type': 'point',
                        'pixel': [x, y],
                    }
                    if smart and target_cam.xyz is not None:
                        _dx = [lm_xyz[k] - target_cam.xyz[k] for k in range(3)]
                        _d = math.sqrt(sum(v * v for v in _dx))
                        if _f_px and _d > 1.0 and (6.0 / _d) * _f_px < 2.0:
                            _smart_hidden += 1
                            continue
                        _entry['_d'] = _d"""
    assert o in src, 'ancre s2 (_entry)'
    src = src.replace(o, n, 1)
    o = """            if assist:
                projections.sort(key=lambda p: (p.get('priority', 3), p['name']))
            self.send_json({
                'cam': cam_name,
                'cam_size': [target_w, target_h],
                'projections': projections,
            })"""
    n = """            if assist:
                projections.sort(key=lambda p: (p.get('priority', 3), p['name']))
            # [ASSIST-SMART-V1] occlusion pairwise sur les points projetes
            if smart:
                _pts = [p for p in projections if p.get('_d') is not None]
                _drop = set()
                for _i in range(len(_pts)):
                    for _j in range(len(_pts)):
                        if _i == _j or _pts[_i]['name'] in _drop:
                            continue
                        _a, _b = _pts[_i], _pts[_j]
                        if _a['_d'] > 1.35 * _b['_d']:
                            _dpx = math.hypot(_a['pixel'][0] - _b['pixel'][0],
                                              _a['pixel'][1] - _b['pixel'][1])
                            if _dpx < 18.0:
                                _drop.add(_a['name'])
                                break
                if _drop:
                    _smart_hidden += len(_drop)
                    projections = [p for p in projections if p.get('name') not in _drop]
            for _p in projections:
                _p.pop('_d', None)
            self.send_json({
                'cam': cam_name,
                'cam_size': [target_w, target_h],
                'smart_hidden': _smart_hidden if smart else None,
                'projections': projections,
            })"""
    assert o in src, 'ancre s3 (send_json)'
    src = src.replace(o, n, 1)
    open(p, 'w').write(src)
    print(f'EDIT {p}: filtres smart 3/3')

p = 'tools/calib.html'
src = open(p).read()
if 'ASSIST-SMART-V1' in src:
    print(f'ok  {p}: deja patche')
    sys.exit(0)
o = "        const r = await fetch('/api/lm_projections?cam=' + encodeURIComponent(cam1) + '&mode=assist');"
n = """        const r = await fetch('/api/lm_projections?cam=' + encodeURIComponent(cam1) + '&mode=assist' +
                              (window._assistSmart === false ? '&smart=0' : ''));   // [ASSIST-SMART-V1]"""
assert o in src, 'ancre u1 (fetch)'
src = src.replace(o, n, 1)
o = """      ghostMarkers1 = (d1 && d1.projections) || [];
      ghostMarkers2 = [];
      renderAssistPanel(ghostMarkers1);"""
n = """      ghostMarkers1 = (d1 && d1.projections) || [];
      ghostMarkers2 = [];
      window._assistHidden = (d1 && d1.smart_hidden) || 0;   // [ASSIST-SMART-V1]
      renderAssistPanel(ghostMarkers1);"""
assert o in src, 'ancre u2 (refresh)'
src = src.replace(o, n, 1)
o = """    const pts = ghosts.filter(g => g.priority === 1 || g.priority === 2).slice(0, 30);
    list.innerHTML = '';"""
n = """    const pts = ghosts.filter(g => g.priority === 1 || g.priority === 2).slice(0, 30);
    list.innerHTML = '';
    // [ASSIST-SMART-V1] footer: compte des masques + toggle
    const smartOn = window._assistSmart !== false;
    const hid = window._assistHidden || 0;
    const foot = document.createElement('div');
    foot.className = 'ap-note';
    foot.style.cursor = 'pointer';
    foot.textContent = smartOn
      ? ('smart: ' + hid + ' ghost(s) masques (occlusion/sub-res) — clic pour tout montrer')
      : 'smart OFF (tout affiche) — clic pour reactiver';
    foot.onclick = () => { window._assistSmart = !smartOn; window._refreshGhosts && window._refreshGhosts(); };
    list.appendChild(foot);"""
assert o in src, 'ancre u3 (panel)'
src = src.replace(o, n, 1)
open(p, 'w').write(src)
print(f'EDIT {p}: smart param + footer toggle 3/3')
