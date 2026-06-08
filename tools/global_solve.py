"""Global bundle adjustment, SHADOW mode. Scoped to one zone.
Soft-anchors cam poses to current values (position prior) to prevent
under-determined cams teleporting to local minima. Hard anchors frozen, Huber loss."""
import sys, numpy as np
from collections import Counter
from scipy.optimize import least_squares
sys.path.insert(0, 'tools')
import refine_cam_ypr as R
import gtamaplib as ml

LEAK = {'A_full_hud','B_pos_fov_player','C_pos_fov_only','Cm_pos_only'}
HARD_LM_ERR = 0.5
ZONE = sys.argv[1] if len(sys.argv) > 1 else 'vice_city'
HUBER = 5.0
POS_PRIOR = 0.5
ANG_PRIOR = 2.0

def main():
    cams, pix, lms, tiers = R.load_all()
    def is_hard_cam(n): return cams[n].get('constraint_class') in LEAK
    def is_hard_lm(n):
        d = lms.get(n); return isinstance(d, dict) and d.get('error_m') is not None and d['error_m'] < HARD_LM_ERR
    def lm_zone(n):
        d = lms.get(n); return d.get('zone') if isinstance(d, dict) else None
    posed = {n: cd for n, cd in cams.items() if cd.get('xyz')}
    def cam_in_zone(cn):
        zs = [lm_zone(lm) for lm in pix.get(cn, {}) if lm_zone(lm)]
        return bool(zs) and Counter(zs).most_common(1)[0][0] == ZONE

    zone_cams = [cn for cn in posed if cam_in_zone(cn)]
    soft_cams = [cn for cn in zone_cams if not is_hard_cam(cn)]
    hard_cams = [cn for cn in zone_cams if is_hard_cam(cn)]
    zone_lms = set()
    for cn in zone_cams:
        for lm in pix.get(cn, {}):
            d = lms.get(lm)
            if isinstance(d, dict) and d.get('xyz') and lm_zone(lm) == ZONE:
                zone_lms.add(lm)
    free_lms = [lm for lm in zone_lms if not is_hard_lm(lm)]
    hard_lms = [lm for lm in zone_lms if is_hard_lm(lm)]

    print("=== GLOBAL SOLVE (SHADOW, soft-anchored) zone=%s ===" % ZONE)
    print("  pos_prior=%.2f ang_prior=%.2f huber=%.1f" % (POS_PRIOR, ANG_PRIOR, HUBER))
    print("  cams: %d (soft %d, hard %d)  landmarks: %d (free %d, hard %d)" % (
        len(zone_cams), len(soft_cams), len(hard_cams), len(zone_lms), len(free_lms), len(hard_lms)))

    cam_idx = {cn: i for i, cn in enumerate(soft_cams)}
    lm_idx = {lm: i for i, lm in enumerate(free_lms)}
    nC, nL = len(soft_cams), len(free_lms)
    cam0 = {cn: (np.array(cams[cn]['xyz']), np.array(cams[cn]['ypr'])) for cn in soft_cams}

    x0 = []
    for cn in soft_cams: x0 += list(cams[cn]['xyz']) + list(cams[cn]['ypr'])
    for lm in free_lms: x0 += list(lms[lm]['xyz'])
    x0 = np.array(x0)
    fixed_cam = {cn: (np.array(cams[cn]['xyz']), np.array(cams[cn]['ypr'])) for cn in hard_cams}
    fixed_lm = {lm: np.array(lms[lm]['xyz']) for lm in hard_lms}

    obs = []
    for cn in zone_cams:
        for lm in pix.get(cn, {}):
            if lm not in zone_lms: continue
            mk = pix[cn][lm]
            if not mk or mk[0] is None: continue
            if cn in cam_idx or lm in lm_idx:
                obs.append((cn, lm, np.array(mk, float)))
    print("  observations: %d   variables: %d   residuals(+priors): %d" % (len(obs), nC*6+nL*3, len(obs)*2 + nC*4))

    def unpack(p):
        poses = {cn: (p[i*6:i*6+3], p[i*6+3:i*6+6]) for cn, i in cam_idx.items()}
        base = nC*6
        lmpos = {lm: p[base+j*3:base+j*3+3] for lm, j in lm_idx.items()}
        return poses, lmpos

    def cam_for(cn, poses):
        cd = cams[cn]
        xyz, ypr = poses[cn] if cn in poses else fixed_cam[cn]
        return ml.Camera(cd.get('id'), cn, cd.get('player'), list(xyz), list(ypr), cd['fov'], cd['size'], cd.get('source'))

    def resid(p):
        poses, lmpos = unpack(p)
        out = []
        for cn, lm, mk in obs:
            obj = cam_for(cn, poses)
            wxyz = lmpos[lm] if lm in lmpos else fixed_lm[lm]
            pr = obj.get_pixel(tuple(wxyz))
            out += [1e3, 1e3] if (pr is None or pr[0] is None) else list(np.array(pr, float) - mk)
        for cn in cam_idx:
            xyz, ypr = poses[cn]
            x0xyz, x0ypr = cam0[cn]
            out += list(POS_PRIOR * (np.array(xyz) - x0xyz))
            out.append(ANG_PRIOR * (ypr[2] - x0ypr[2]))
        return out

    print("  solving...")
    res = least_squares(resid, x0, method='trf', loss='huber', f_scale=HUBER, max_nfev=300)
    poses, lmpos = unpack(res.x)

    def rms_after(cn):
        obj = cam_for(cn, poses); es = []
        for lm in pix.get(cn, {}):
            if lm not in zone_lms: continue
            mk = pix[cn][lm]
            if not mk or mk[0] is None: continue
            wxyz = lmpos[lm] if lm in lmpos else (fixed_lm.get(lm) if lm in fixed_lm else (np.array(lms[lm]['xyz']) if lms.get(lm,{}).get('xyz') else None))
            if wxyz is None: continue
            pr = obj.get_pixel(tuple(wxyz))
            if pr is None or pr[0] is None: continue
            es.append(float(np.linalg.norm(np.array(pr,float)-np.array(mk,float))))
        return (np.sqrt(np.mean(np.square(es))) if es else 0, len(es))

    def rms_before(cn):
        cd = cams[cn]; obj = ml.Camera(cd.get('id'), cn, cd.get('player'), cd['xyz'], cd['ypr'], cd['fov'], cd['size'], cd.get('source'))
        es = []
        for lm in pix.get(cn, {}):
            if lm not in zone_lms: continue
            mk = pix[cn][lm]
            if not mk or mk[0] is None: continue
            pr = obj.get_pixel(tuple(lms[lm]['xyz']))
            if pr is None or pr[0] is None: continue
            es.append(float(np.linalg.norm(np.array(pr,float)-np.array(mk,float))))
        return np.sqrt(np.mean(np.square(es))) if es else 0

    print("\n  %-32s %7s %7s %5s %7s" % ('cam','before','after','nLM','moved_m'))
    imp = wor = 0
    for cn in soft_cams:
        b = rms_before(cn); a, n = rms_after(cn)
        moved = float(np.linalg.norm(poses[cn][0] - cam0[cn][0]))
        tag = ''
        if n and b > 0:
            if a < b - 1: imp += 1; tag = '  IMPROVED'
            elif a > b + 1: wor += 1; tag = '  <-- WORSE'
        warn = '  !!BIG MOVE' if moved > 40 else ''
        print("  %-32s %7.1f %7.1f %5d %7.1f%s%s" % (cn[:32], b, a, n, moved, tag, warn))
    print("\n  improved: %d  worsened: %d" % (imp, wor))
    print("  (BIG MOVE >40m on low-nLM cams = verify before trusting)")

    print("\n  TOP OUTLIERS after solve (>15px):")
    outs = []
    for cn, lm, mk in obs:
        obj = cam_for(cn, poses)
        wxyz = lmpos[lm] if lm in lmpos else fixed_lm[lm]
        pr = obj.get_pixel(tuple(wxyz))
        if pr is None or pr[0] is None: continue
        e = float(np.linalg.norm(np.array(pr,float)-mk))
        if e > 15: outs.append((e, cn, lm))
    outs.sort(reverse=True)
    for e, cn, lm in outs[:15]:
        print("    %7.0fpx  %s sees %s" % (e, cn, lm))
    print("\n  SHADOW MODE: nothing written.")

if __name__ == '__main__':
    main()
