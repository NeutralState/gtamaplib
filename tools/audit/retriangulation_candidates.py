#!/usr/bin/env python3
"""
retriangulation_candidates.py - READ-ONLY audit (Chantier A, etape A1).
Scanne tous les LM, rejoue observers -> classify_cam -> select_sources ->
robust_triangulate, et classe par gain de retriangulation. AUCUNE ECRITURE.
"""
import argparse, itertools, math, os, sys
import numpy as np
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.dirname(THIS_DIR)
sys.path.insert(0, TOOLS_DIR)
import triangulate_lm as T

PARALLAX_MIN = 15.0

def best_pairwise_parallax(cams, lm_name, pixels):
    rays = T._build_rays(cams, lm_name, pixels)
    best = 0.0
    for (_, _, d1), (_, _, d2) in itertools.combinations(rays, 2):
        cosang = float(np.clip(np.dot(d1, d2), -1.0, 1.0))
        best = max(best, math.degrees(math.acos(cosang)))
    return best, len(rays)

def class_tally(oc):
    order = [('leak_a','A'),('leak_pos','Lp'),('trusted_non_leak','Tr'),('other','Ot'),('excluded','Ex')]
    counts = {}
    for c in oc.values():
        counts[c] = counts.get(c, 0) + 1
    return "/".join(f"{abbr}{counts.get(k, 0)}" for k, abbr in order)

def annotate_sources(names, cameras):
    out = []
    for n in names:
        cc = (cameras.get(n, {}) or {}).get('constraint_class')
        out.append(f"{n}[{cc}]" if cc else n)
    return ", ".join(out)

def fmt(v, spec=""):
    if v is None:
        return "-"
    return format(v, spec) if spec else str(v)

def main():
    ap = argparse.ArgumentParser(description="READ-ONLY audit: rank LMs by retriangulation gain (A1).")
    ap.add_argument('--delta-min', type=float, default=2.0)
    ap.add_argument('--lm', default=None)
    ap.add_argument('--limit', type=int, default=None)
    args = ap.parse_args()
    cameras, pixels, landmarks, cam_tiers = T.load_all()
    observers_by_lm = {}
    for cam_name, lm_map in pixels.items():
        if not isinstance(lm_map, dict):
            continue
        for lm_name in lm_map:
            observers_by_lm.setdefault(lm_name, []).append(cam_name)
    lm_names = list(landmarks.keys())
    if args.lm:
        lm_names = [n for n in lm_names if args.lm.lower() in n.lower()]
    if args.limit is not None:
        lm_names = lm_names[:args.limit]
    cand, near, nobase, skip = [], [], [], []
    total = len(lm_names)
    for i, lm_name in enumerate(lm_names, 1):
        if i % 25 == 0 or i == total:
            print(f"  ... {i}/{total}", file=sys.stderr)
        try:
            lm = landmarks.get(lm_name)
            if not isinstance(lm, dict):
                skip.append((lm_name, 0, "-", None, None, 0, None, None, 0, "-", "not a dict"))
                continue
            cur_xyz = lm.get('xyz')
            cur_sources = lm.get('source_cameras', []) or []
            observers = observers_by_lm.get(lm_name, [])
            if not observers:
                skip.append((lm_name, 0, "-", None, None, 0, None, None, len(cur_sources), "-", "no observers"))
                continue
            oc = {cn: T.classify_cam(cn, cameras, cam_tiers) for cn in observers}
            tally = class_tally(oc)
            candidate, reason = T.select_sources(oc)
            if len(candidate) < 2:
                skip.append((lm_name, len(observers), tally, None, None, 0, None, None, len(cur_sources), "-", reason or "insufficient observers"))
                continue
            par_pool, _ = best_pairwise_parallax(candidate, lm_name, pixels)
            init = cur_xyz if cur_xyz else [0.0, 0.0, 0.0]
            xyz_new, max_res, kept, dropped = T.robust_triangulate(candidate, lm_name, pixels, cameras, init, verbose=False, observers_classified_global=oc)
            if xyz_new is None:
                skip.append((lm_name, len(observers), tally, par_pool, None, 0, None, None, len(cur_sources), "-", str(max_res)))
                continue
            par_kept, _ = best_pairwise_parallax(kept, lm_name, pixels)
            kept_ann = annotate_sources(kept, cameras)
            if not cur_xyz:
                nobase.append((lm_name, len(observers), tally, par_pool, par_kept, len(kept), None, max_res, len(cur_sources), kept_ann, "no current xyz (new LM)"))
                continue
            delta = math.sqrt(sum((xyz_new[k] - cur_xyz[k]) ** 2 for k in range(3)))
            crit = []
            if par_kept < PARALLAX_MIN:
                crit.append(f"par_kept {par_kept:.1f}<{PARALLAX_MIN:g}")
            if delta < args.delta_min:
                crit.append(f"delta {delta:.2f}<{args.delta_min:g}")
            if len(kept) < 2:
                crit.append(f"kept {len(kept)}<2")
            row = (lm_name, len(observers), tally, par_pool, par_kept, len(kept), delta, max_res, len(cur_sources), kept_ann, "GAIN" if not crit else "; ".join(crit))
            (cand if not crit else near).append(row)
        except Exception as e:
            skip.append((lm_name, 0, "-", None, None, 0, None, None, 0, "-", f"audit error: {type(e).__name__}: {e}"))
    cand.sort(key=lambda r: r[6], reverse=True)
    near.sort(key=lambda r: (r[6] if r[6] is not None else -1.0), reverse=True)
    nobase.sort(key=lambda r: (r[7] if r[7] is not None else 1e9))
    skip.sort(key=lambda r: r[10])
    hdr = ("TAG","LM","n_obs","classes(A/Lp/Tr/Ot/Ex)","par_pool","par_kept","n_kept","delta_m","max_res'","cur_n","kept_sources","reason")
    def emit(tag, rows):
        for r in rows:
            (lm_name, n_obs, tally, par_pool, par_kept, n_kept, delta, max_res, cur_n, kept_ann, reason) = r
            cols = [tag, lm_name, fmt(n_obs), tally, fmt(par_pool, ".2f"), fmt(par_kept, ".2f"), fmt(n_kept), fmt(delta, ".3f"), fmt(max_res, ".2f"), fmt(cur_n), kept_ann, reason]
            print("\t".join(cols))
    print("\t".join(hdr))
    print(f"# delta_min={args.delta_min:g} m  parallax_min={PARALLAX_MIN:g} deg  (dedup 5deg + outlier rejection internes a robust_triangulate)")
    print(f"# CANDIDATS={len(cand)}  QUASI={len(near)}  NO_BASELINE={len(nobase)}  SKIP={len(skip)}  total={total}")
    print()
    print("### CANDIDATS (gain flagge - par_kept>=15, delta>=min, kept>=2) - tri delta desc")
    emit("CAND", cand)
    print()
    print("### QUASI (triangule sain mais un critere tombe) - tri delta desc")
    emit("NEAR", near)
    print()
    print("### NO_BASELINE (pas de xyz courant - delta non calculable)")
    emit("NOBASE", nobase)
    print()
    print("### SKIP (non retriangulable) - tri par raison")
    emit("SKIP", skip)
    return 0

if __name__ == '__main__':
    sys.exit(main())
