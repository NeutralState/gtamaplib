import sys, numpy as np
from collections import defaultdict
sys.path.insert(0, 'tools')
import refine_cam_ypr as R
import gtamaplib as ml

LEAK = {'A_full_hud','B_pos_fov_player','C_pos_fov_only','Cm_pos_only'}
HARD_LM_ERR = 0.5

def main():
    cams, pix, lms, tiers = R.load_all()
    def cam_obj(name):
        cd = cams[name]
        return ml.Camera(cd.get('id'), name, cd.get('player'), cd['xyz'], cd['ypr'], cd['fov'], cd['size'], cd.get('source'))
    def is_hard_cam(name):
        return cams[name].get('constraint_class') in LEAK
    def is_hard_lm(name):
        d = lms.get(name)
        return isinstance(d, dict) and d.get('error_m') is not None and d['error_m'] < HARD_LM_ERR
    posed = {n: cd for n, cd in cams.items() if cd.get('xyz')}

    print("="*70)
    print("OBSERVABILITY REPORT")
    print("="*70)

    print("\n[1] STALE POSITIONS (stored 3D vs markings, >15px on a viewer)")
    stale = []
    for lm, d in lms.items():
        if not isinstance(d, dict) or not d.get('xyz'):
            continue
        worst = 0.0; worst_cam = None
        for cn in posed:
            if lm not in pix.get(cn, {}):
                continue
            mk = pix[cn][lm]
            if not mk or mk[0] is None:
                continue
            try:
                pr = cam_obj(cn).get_pixel(tuple(d['xyz']))
                e = 9999 if (pr is None or pr[0] is None) else float(np.linalg.norm(np.array(pr,float)-np.array(mk,float)))
            except Exception:
                continue
            if e > worst:
                worst, worst_cam = e, cn
        if worst > 15:
            stale.append((worst, lm, worst_cam))
    stale.sort(reverse=True)
    print("    %d landmarks with stale/inconsistent position:" % len(stale))
    for e, lm, cn in stale[:20]:
        print("      %8.0fpx  %s  (worst on %s)" % (e, lm, cn))

    print("\n[2] UNDER-DETERMINED LANDMARKS")
    one_view = []; all_soft = []
    for lm, d in lms.items():
        if not isinstance(d, dict) or not d.get('xyz'):
            continue
        viewers = [cn for cn in posed if lm in pix.get(cn, {})]
        if len(viewers) < 2:
            one_view.append((lm, viewers))
        elif not any(is_hard_cam(cn) for cn in viewers) and not is_hard_lm(lm):
            all_soft.append((lm, viewers))
    print("    %d landmarks seen by <2 posed cams (not triangulable)" % len(one_view))
    print("    %d landmarks seen only by soft cams AND not hard (floating)" % len(all_soft))
    for lm, v in all_soft[:12]:
        print("      %s  (%d soft viewers)" % (lm, len(v)))

    print("\n[3] ANCHOR GRAPH (soft cams: how many HARD landmarks observed)")
    soft_cams = [n for n in posed if not is_hard_cam(n)]
    rows = []
    for cn in soft_cams:
        seen = [lm for lm in pix.get(cn, {}) if is_hard_lm(lm)]
        rows.append((len(seen), cn))
    rows.sort()
    starved = [r for r in rows if r[0] < 2]
    print("    %d/%d soft cams see <2 hard landmarks (under-anchored):" % (len(starved), len(soft_cams)))
    for n, cn in starved[:25]:
        print("      %d hard LMs  %s (%s)" % (n, cn, cams[cn].get('constraint_class')))

    print("\n[4] PER-ZONE SOLIDITY")
    zone_stats = defaultdict(lambda: {'lm':0,'hard':0,'stale':0})
    stale_lms = {lm for _, lm, _ in stale}
    for lm, d in lms.items():
        if not isinstance(d, dict) or not d.get('xyz'):
            continue
        z = d.get('zone', 'unknown')
        zone_stats[z]['lm'] += 1
        if is_hard_lm(lm): zone_stats[z]['hard'] += 1
        if lm in stale_lms: zone_stats[z]['stale'] += 1
    print("    %-24s %5s %6s %7s %6s" % ('zone','#lm','#hard','#stale','hard%'))
    for z, s in sorted(zone_stats.items(), key=lambda kv: -kv[1]['lm']):
        pct = 100*s['hard']/s['lm'] if s['lm'] else 0
        flag = '  <-- FLOATING' if pct < 15 and s['lm'] > 5 else ''
        print("    %-24s %5d %6d %7d %5.0f%%%s" % (str(z), s['lm'], s['hard'], s['stale'], pct, flag))

    print("\n[5] SUMMARY")
    print("    cameras posed: %d (hard %d, soft %d)" % (len(posed), sum(1 for n in posed if is_hard_cam(n)), len(soft_cams)))
    print("    hard landmarks: %d" % sum(1 for lm in lms if is_hard_lm(lm)))
    print("    STALE positions: %d" % len(stale))
    print("    under-anchored soft cams: %d" % len(starved))
    print("    floating landmarks: %d" % len(all_soft))

if __name__ == '__main__':
    main()
