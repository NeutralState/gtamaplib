"""Patch serveur ASSIST-V1: mode=assist sur /api/lm_projections.

Ajoute un scoring de priorite par ghost:
  P1 = 2e source (triangulation instantanee) ou ancre pour cam sous-observee
  P2 = ancre redondante ou source de plus vers un meilleur tier
  P3 = couverture

Usage: python3 patch_assist_server.py  (depuis la racine du repo). Idempotent.
Backup: tools/server.py.bak_assist
"""
import shutil, sys

P = 'tools/server.py'
s = open(P).read()
if 'ASSIST-V1' in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_assist')

old = """            projections = []
            VIRTUAL_PREFIXES = ('Portofino Tower (',)
            # If a filter_cam is given, restrict to LMs marked on it.
            filter_set = None
            if filter_cam and filter_cam in md.cameras:
                filter_set = set(md.pixels.get(filter_cam, {}).keys())"""
new = """            # [ASSIST-V1] mode=assist: single-cam marking assistant. No
            # filter_cam; every projectable unmarked LM is returned with a
            # priority score describing what marking it would unlock.
            assist = qs.get('mode', [''])[0] == 'assist'
            _tiers_path = os.path.join(TOOL_DIR, 'generated', 'confidence_tiers.json')
            _lm_tier, _cam_meta = {}, {}
            if assist and os.path.exists(_tiers_path):
                try:
                    with open(_tiers_path) as _f:
                        _t = json.load(_f)
                    _lm_tier = {k: v.get('tier') for k, v in _t.get('landmarks', {}).items()}
                    _cam_meta = _t.get('cameras', {}).get(cam_name, {})
                except Exception:
                    pass
            _cam_n_obs = _cam_meta.get('n_obs', 99)

            def _assist_score(lm_name, n_src):
                lt = _lm_tier.get(lm_name)
                if n_src == 1:
                    return 1, '2e source -> triangulation'
                if lt in ('anchor', 'high') and _cam_n_obs < 5:
                    return 1, 'ancre pour cette cam sous-observee'
                if lt in ('anchor', 'high'):
                    return 2, 'ancre (redondance utile)'
                if lt in ('low', 'medium'):
                    return 2, 'source de plus -> tier'
                return 3, 'couverture'

            projections = []
            VIRTUAL_PREFIXES = ('Portofino Tower (',)
            # If a filter_cam is given, restrict to LMs marked on it.
            filter_set = None
            if filter_cam and filter_cam in md.cameras:
                filter_set = set(md.pixels.get(filter_cam, {}).keys())"""
assert old in s, 'bloc projections introuvable'
s = s.replace(old, new)

old2 = """                    projections.append({
                        'name': lm_name,
                        'type': 'point',
                        'pixel': [x, y],
                    })"""
new2 = """                    _entry = {
                        'name': lm_name,
                        'type': 'point',
                        'pixel': [x, y],
                    }
                    if assist:
                        _p, _r = _assist_score(lm_name, len(src_cams))
                        _entry.update({'priority': _p, 'reason': _r,
                                       'tier': _lm_tier.get(lm_name),
                                       'n_sources': len(src_cams)})
                    projections.append(_entry)"""
assert old2 in s
s = s.replace(old2, new2)

old3 = """                        projections.append({
                            'name': lm_name,
                            'type': 'epipolar',
                            'line': [[x1, y1], [x2, y2]],
                            'source_cam': src_cam_name,
                        })"""
new3 = """                        _entry = {
                            'name': lm_name,
                            'type': 'epipolar',
                            'line': [[x1, y1], [x2, y2]],
                            'source_cam': src_cam_name,
                        }
                        if assist:
                            _entry.update({'priority': 1,
                                           'reason': '2e source -> triangulation (ligne epipolaire)',
                                           'tier': _lm_tier.get(lm_name),
                                           'n_sources': 1})
                        projections.append(_entry)"""
assert old3 in s
s = s.replace(old3, new3)

old4 = """            self.send_json({
                'cam': cam_name,
                'cam_size': [target_w, target_h],
                'projections': projections,
            })"""
new4 = """            if assist:
                projections.sort(key=lambda p: (p.get('priority', 3), p['name']))
            self.send_json({
                'cam': cam_name,
                'cam_size': [target_w, target_h],
                'projections': projections,
            })"""
assert old4 in s
s = s.replace(old4, new4)
open(P, 'w').write(s)
print('ASSIST-V1 serveur patche. Backup: tools/server.py.bak_assist')
