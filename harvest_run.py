"""harvest_run.py — gated marking harvest (proto of auto_harvest, 2026-07-04).

Scans every LM that became triangulable (no xyz, 2+ obs) or upgradable
(existing xyz, new observer, <=2 sources), dry-runs each through
triangulate_lm, and applies ONLY those passing the gates:
  - max residual < 8 arcmin
  - upgrades additionally: xyz delta < 15 m (bigger moves -> review list)
Resumable (state file in /tmp). Run, then compute tiers + CI + commit.
Usage: PYTHONPATH=. python3 harvest_run.py
"""
import sys, subprocess, os, re, json
sys.path.insert(0, '.')
import gtamapdata as md

STATE = '/tmp/gtamaplib_harvest_state.json'
state = json.load(open(STATE)) if os.path.exists(STATE) else {'done': [], 'applied': [], 'refused': [], 'review': []}
done = set(state['done'])

tri = []
for lm in set(ln for d in md.pixels.values() for ln in d):
    if md.landmarks.get(lm) is not None: continue
    obs = [c for c, d in md.pixels.items() if lm in d and d[lm] is not None]
    if len(obs) >= 2: tri.append(lm)
upg = []
for lm, xyz in md.landmarks.items():
    if xyz is None: continue
    src = set((md.landmarks_meta.get(lm) or {}).get('source_cameras', []) or [])
    obs = {c for c, d in md.pixels.items() if lm in d and d[lm] is not None}
    if (obs - src) and len(src) <= 2: upg.append(lm)

todo = [('tri', l) for l in sorted(tri) if 'tri:'+l not in done] + \
       [('upg', l) for l in sorted(upg) if 'upg:'+l not in done]
print(f'reste: {len(todo)}')
import time
t0 = time.time()
for kind, lm in todo:
    pass  # no time cap on user machine
    r = subprocess.run([sys.executable, 'tools/triangulate_lm.py', lm],
                       capture_output=True, text=True, timeout=60,
                       env={**os.environ, 'PYTHONPATH': '.'})
    mx = re.search(r'Max residual: ([\d.]+)', r.stdout)
    dl = re.search(r'Delta from current: ([\d.]+)', r.stdout)
    ao = re.search(r'All-observer residual: max ([\d.]+)', r.stdout)
    why = re.search(r'reason: (.+)', r.stdout)
    key = kind + ':' + lm
    if mx is None:
        state['refused'].append((kind, lm, (why.group(1).strip() if why else 'dry fail')[:60]))
    else:
        mxv = float(mx.group(1)); dlv = float(dl.group(1)) if dl else None
        # SIGMA-GATES-V1: la gate delta devient relative a l'incertitude du
        # LM (COVARIANCE-V1): un move <= 3*sigma est statistiquement
        # insignifiant meme s'il depasse 15m (ex: Water Tower near Prison
        # 18m avec sigma=32.5m). Plancher 15 conserve pour les LM hors solve.
        try:
            sys.path.insert(0, 'tools')
            from common import lm_sigma_m
            _sig = lm_sigma_m(lm)
        except Exception:
            _sig = None
        gate_d = max(15.0, 3.0 * _sig) if _sig is not None else 15.0
        # OBSERVER-GUARD-V1 (regle Flagler en code): le point propose doit
        # satisfaire TOUS les observers non-exclus (<8'), pas juste le pool.
        aov = float(ao.group(1)) if ao else None
        obs_ok = (aov is None) or (aov < 8)
        ok = mxv < 8 and obs_ok and (kind == 'tri' or (dlv is not None and dlv < gate_d))
        if ok:
            subprocess.run([sys.executable, 'tools/triangulate_lm.py', lm, '--apply'],
                           capture_output=True, text=True, timeout=60,
                           env={**os.environ, 'PYTHONPATH': '.'})
            state['applied'].append((kind, lm, mxv, dlv))
        elif mxv < 8:
            why_rev = f'all-obs {aov:.1f}' if (aov is not None and aov >= 8) else f'delta {dlv}'
            state['review'].append((kind, lm, mxv, dlv, why_rev))
        else:
            state['refused'].append((kind, lm, f'resid {mxv:.0f}'))
    state['done'].append(key)
    json.dump(state, open(STATE, 'w'))
print(f'traites: {len(state["done"])} | appliques: {len(state["applied"])} | review: {len(state["review"])} | refuses: {len(state["refused"])}')
