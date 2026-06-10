#!/usr/bin/env python3
"""guarded_apply.py — Disk-verified selective apply of bundle_adjust_result.json.

Problem this solves (proven 2026-06-10 full-rerun experiment): a global BA can
report -80% on its own weighted loss while WORSENING 29/95 cams at equal weight,
because shared LMs get dragged to a compromise that sacrifices leak-cam rays
(e.g. Pool 0'->416', Police Chase (D) leak 1.6'->133' without the cams moving).

Strategy: hill-climbing over individual deltas.
  Candidates = each LM move, each cam move, and each (cam + its updated child
  LMs) bundle. A candidate is ACCEPTED only if, re-evaluated on the CURRENT
  accepted state with the exact tier formula (dx*hfov/w*60):
    - no affected cam regresses more than --tol arcmin (default 0.25), AND
    - net sum of affected-cam RMS strictly improves.
  Multi-pass until a full pass accepts nothing.

Doctrine blacklist (cam moves never applied): Amphitheater (contradictory hard
anchors, stays on rlx pose), Beach (ground-projection cam, z/pitch critical,
pixel RMS does not capture coastline quality), Vice City Sign (2-LM
under-determined, BA teleports it 68m with full freedom).

Dry-run by default; --apply writes via md.update_camera/update_landmark and
backs up .bak_guarded first.
"""
import argparse, copy, json, math, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(ROOT)) if os.path.basename(ROOT) == "tools" else None
PROJ = os.path.dirname(ROOT) if os.path.basename(ROOT) == "tools" else ROOT
sys.path.insert(0, PROJ)

import gtamaplib as ml
import gtamapdata as md

CAM_BLACKLIST_DEFAULT = ["Amphitheater", "Beach", "Vice City Sign"]


def snap_z(lm_name, xyz):
    """Apply the SAME z_constraint snap that md.update_landmark applies at write
    time, so the guard validates exactly the geometry that will hit the disk
    (lesson: 2026-06-10, Island G/K — free-z validated, snapped-z written)."""
    meta = md.landmarks_meta.get(lm_name) or {}
    zc = meta.get("z_constraint")
    if zc and zc.get("type") == "fixed":
        xyz = list(xyz)
        xyz[2] = float(zc["value"])
    return list(xyz)


def build_state():
    cams = {n: {"xyz": list(c["xyz"]), "ypr": list(c["ypr"]), "fov": list(c["fov"])}
            for n, c in md.cameras.items()}
    lms = {n: (list(xyz) if xyz is not None else None) for n, xyz in md.landmarks.items()}
    return cams, lms


def cam_rms(cam_name, cams, lms, _cache={}):
    """RMS arcmin for cam_name under in-memory state. Same formula as tiers."""
    obs = md.pixels.get(cam_name)
    if not obs or cam_name not in cams:
        return None
    cam = ml.get_camera(cam_name)
    st = cams[cam_name]
    cam.set_xyz(tuple(st["xyz"]))
    cam.set_ypr(tuple(st["ypr"]))
    cam.set_fov(tuple(st["fov"]))
    acc, n = 0.0, 0
    for lm_name, pixel in obs.items():
        xyz = lms.get(lm_name)
        if xyz is None or pixel is None:
            continue
        try:
            proj = cam.get_pixel(xyz)
            if proj is None:
                continue
            dx = (proj[0] - pixel[0]) * cam.hfov / cam.w * 60
            dy = (proj[1] - pixel[1]) * cam.vfov / cam.h * 60
            acc += dx * dx + dy * dy
            n += 1
        except Exception:
            continue
    return math.sqrt(acc / n) if n else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", default=os.path.join(PROJ, "tools", "bundle_adjust_result.json"))
    ap.add_argument("--tol", type=float, default=0.25, help="max per-cam regression accepted (arcmin)")
    ap.add_argument("--blacklist-cam", nargs="*", default=CAM_BLACKLIST_DEFAULT)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    with open(args.result) as f:
        result = json.load(f)
    cam_updates = result.get("cameras", {})
    lm_updates = result.get("landmarks", {})

    # observers index: lm -> cams that mark it
    observers = {}
    for c, obs in md.pixels.items():
        for l in obs:
            observers.setdefault(l, set()).add(c)

    cams, lms = build_state()

    # baseline RMS for EVERY cam: regression budget is cumulative vs this,
    # so many small accepted deltas can never silently stack on one victim.
    baseline0 = {c: cam_rms(c, cams, lms) for c in md.pixels if c in cams}

    def affected_for(delta):
        aff = set()
        for cn in delta.get("cams", {}):
            aff.add(cn)
            # moving a cam changes nothing for others directly (LMs handled separately)
        for ln in delta.get("lms", {}):
            aff |= observers.get(ln, set())
        return {a for a in aff if a in md.pixels}

    def try_delta(delta):
        aff = affected_for(delta)
        if not aff:
            return False, 0.0
        before = {a: cam_rms(a, cams, lms) for a in aff}
        # stage
        staged_c = {cn: copy.deepcopy(cams[cn]) for cn in delta.get("cams", {}) if cn in cams}
        staged_l = {ln: list(lms[ln]) for ln in delta.get("lms", {}) if ln in lms}
        for cn, upd in delta.get("cams", {}).items():
            if cn in cams:
                if upd.get("xyz") is not None: cams[cn]["xyz"] = list(upd["xyz"])
                if upd.get("ypr") is not None: cams[cn]["ypr"] = list(upd["ypr"])
                if upd.get("hfov") is not None: cams[cn]["fov"] = [upd["hfov"], None]
                elif upd.get("fov") is not None: cams[cn]["fov"] = list(upd["fov"])
        for ln, xyz in delta.get("lms", {}).items():
            if ln in lms and lms[ln] is not None:
                lms[ln] = list(xyz)
        after = {a: cam_rms(a, cams, lms) for a in aff}
        valid = [a for a in aff if before[a] is not None and after[a] is not None]
        # cumulative guard: regression measured against the session baseline
        worst = max((after[a] - (baseline0.get(a) if baseline0.get(a) is not None else before[a])) for a in valid)
        net = sum((after[a] - before[a]) for a in valid)
        if worst <= args.tol and net < -1e-6:
            return True, net
        # rollback
        for cn, st in staged_c.items():
            cams[cn] = st
        for ln, xyz in staged_l.items():
            lms[ln] = xyz
        return False, net

    # build candidates
    candidates = []
    for ln, xyz in lm_updates.items():
        candidates.append({"name": f"LM {ln}", "lms": {ln: snap_z(ln, xyz)}})
    for cn, upd in cam_updates.items():
        if cn in args.blacklist_cam:
            continue
        candidates.append({"name": f"CAM {cn}", "cams": {cn: upd}})
        child = {l: snap_z(l, lm_updates[l]) for l in md.pixels.get(cn, {}) if l in lm_updates}
        if child:
            candidates.append({"name": f"BUNDLE {cn} (+{len(child)} LMs)", "cams": {cn: upd}, "lms": child})

    accepted, n_pass = [], 0
    while True:
        n_pass += 1
        got = 0
        for cand in candidates:
            if cand.get("_done"):
                continue
            ok, net = try_delta(cand)
            if ok:
                cand["_done"] = True
                accepted.append((cand["name"], net))
                got += 1
        print(f"# pass {n_pass}: accepted {got}")
        if got == 0:
            break

    rejected = [c["name"] for c in candidates if not c.get("_done")]
    print(f"\n# ACCEPTED {len(accepted)} deltas | REJECTED {len(rejected)} | tol={args.tol}' | blacklist={args.blacklist_cam}")
    for name, net in sorted(accepted, key=lambda x: x[1])[:15]:
        print(f"  {net:+9.2f}'  {name}")
    if len(accepted) > 15:
        print(f"  ... +{len(accepted)-15} more")

    if not args.apply:
        print("\nDRY-RUN. Re-run with --apply to write.")
        return

    for p in ("cameras.json", "landmarks.json"):
        shutil.copy(os.path.join(PROJ, "gtamapdata", p), os.path.join(PROJ, "gtamapdata", p + ".bak_guarded"))
    n_c = n_l = 0
    base_cams, _ = build_state()
    for cn, st in cams.items():
        if st != base_cams.get(cn):
            md.update_camera(cn, xyz=st["xyz"], ypr=st["ypr"], fov=st["fov"])
            n_c += 1
    for ln, xyz in lms.items():
        if xyz is None:
            continue
        cur = md.landmarks.get(ln)
        if cur is None or list(cur) != list(xyz):
            md.update_landmark(ln, xyz)
            n_l += 1
    print(f"\nAPPLIED: {n_c} cams, {n_l} landmarks written (backups .bak_guarded).")


if __name__ == "__main__":
    main()
