#!/usr/bin/env python3
"""
tension_audit.py -- WAR-SCAN niveau 2: structure de conflit des deltas rejetes.

Genese 2026-07-06: chaque cycle guarded rejette ~460 deltas et ce sont TOUJOURS
les memes. Le guard sait pourquoi il rejette mais jette l'information. Ce tool
la capture: pour chaque candidat de bundle_adjust_result.json (memes candidats
que guarded_apply, blacklist respectee), evalue UNE fois depuis l'etat disque
propre (rollback systematique, READ-ONLY):
  - gain_potentiel = somme des ameliorations sur les cams qui s'ameliorent
  - bloqueurs      = cams dont la regression depasse --tol, avec magnitude
  - mediateurs     = LMs du delta que chaque bloqueur observe (canal du conflit)
Sorties: top tensions / leaderboard bloqueurs / leaderboard LM charnieres.
Usage:
  python3 tools/bundle_adjust_weighted.py --cleanup --max-iter 30
  PYTHONPATH=. python3 tools/audit/tension_audit.py [--tol 0.25] [--top 20]
"""
import argparse, copy, json, os, sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import gtamapdata as md
from common import cam_rms as _common_cam_rms

CAM_BLACKLIST = ["Amphitheater", "Beach", "Vice City Sign"]


def snap_z(lm_name, xyz):
    meta = md.landmarks_meta.get(lm_name) or {}
    zc = meta.get("z_constraint")
    if zc and zc.get("type") == "fixed":
        xyz = list(xyz)
        xyz[2] = float(zc["value"])
    return list(xyz)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--result', default='tools/bundle_adjust_result.json')
    ap.add_argument('--tol', type=float, default=0.25)
    ap.add_argument('--top', type=int, default=20)
    args = ap.parse_args()

    result = json.load(open(args.result))
    cam_updates = result.get('cameras', {})
    lm_updates = result.get('landmarks', {})

    observers = {}
    for c, obs in md.pixels.items():
        for l in obs:
            observers.setdefault(l, set()).add(c)

    cams = {n: {"xyz": list(c["xyz"]), "ypr": list(c["ypr"]), "fov": list(c["fov"])}
            for n, c in md.cameras.items()}
    lms = {n: (list(xyz) if xyz is not None else None) for n, xyz in md.landmarks.items()}

    def cam_rms(cn):
        return _common_cam_rms(cn, cam_state=cams.get(cn), lms=lms)

    baseline = {c: cam_rms(c) for c in md.pixels if c in cams}

    candidates = []
    for ln, xyz in lm_updates.items():
        candidates.append({"name": f"LM {ln}", "lms": {ln: snap_z(ln, xyz)}})
    for cn, upd in cam_updates.items():
        if cn in CAM_BLACKLIST:
            continue
        candidates.append({"name": f"CAM {cn}", "cams": {cn: upd}})
        child = {l: snap_z(l, lm_updates[l]) for l in md.pixels.get(cn, {}) if l in lm_updates}
        if child:
            candidates.append({"name": f"BUNDLE {cn} (+{len(child)} LMs)",
                               "cams": {cn: upd}, "lms": child})

    tensions = []
    blocker_score = defaultdict(lambda: [0, 0.0])
    mediator_score = defaultdict(lambda: [0, 0.0])

    for cand in candidates:
        aff = set()
        for cn in cand.get("cams", {}):
            aff.add(cn)
        for ln in cand.get("lms", {}):
            aff |= observers.get(ln, set())
        aff = {a for a in aff if a in md.pixels and a in cams}
        if not aff:
            continue
        before = {a: cam_rms(a) for a in aff}
        staged_c = {cn: copy.deepcopy(cams[cn]) for cn in cand.get("cams", {}) if cn in cams}
        staged_l = {ln: (list(lms[ln]) if lms[ln] is not None else None)
                    for ln in cand.get("lms", {}) if ln in lms}
        for cn, upd in cand.get("cams", {}).items():
            if cn in cams:
                if upd.get("xyz") is not None: cams[cn]["xyz"] = list(upd["xyz"])
                if upd.get("ypr") is not None: cams[cn]["ypr"] = list(upd["ypr"])
                if upd.get("hfov") is not None: cams[cn]["fov"] = [upd["hfov"], None]
                elif upd.get("fov") is not None: cams[cn]["fov"] = list(upd["fov"])
        for ln, xyz in cand.get("lms", {}).items():
            if ln in lms and lms[ln] is not None:
                lms[ln] = list(xyz)
        after = {a: cam_rms(a) for a in aff}
        for cn, st in staged_c.items():
            cams[cn] = st
        for ln, xyz in staged_l.items():
            lms[ln] = xyz

        valid = [a for a in aff if before[a] is not None and after[a] is not None]
        if not valid:
            continue
        gains = {a: before[a] - after[a] for a in valid if after[a] < before[a]}
        regressions = {a: after[a] - (baseline[a] if baseline.get(a) is not None else before[a])
                       for a in valid}
        blockers = {a: r for a, r in regressions.items() if r > args.tol}
        gain_pot = sum(gains.values())
        net = sum(after[a] - before[a] for a in valid)
        accepted = (not blockers) and net < -1e-6
        if accepted or gain_pot <= args.tol:
            continue

        med = defaultdict(list)
        delta_lms = set(cand.get("lms", {}))
        for b in blockers:
            shared = sorted(delta_lms & set(md.pixels.get(b, {})))[:4]
            med[b] = shared
            blocker_score[b][0] += 1
            blocker_score[b][1] += gain_pot
            for l in shared:
                mediator_score[l][0] += 1
                mediator_score[l][1] += gain_pot / max(1, len(shared))
        tensions.append({
            "name": cand["name"], "gain": gain_pot, "net": net,
            "blockers": sorted(blockers.items(), key=lambda x: -x[1]),
            "med": med,
        })

    tensions.sort(key=lambda t: -t["gain"])
    print(f"TENSION-AUDIT: {len(tensions)} deltas rejetes avec gain bloque > {args.tol}'  "
          f"(sur {len(candidates)} candidats)\n")

    print(f"=== TOP {args.top} TENSIONS (gain bloque | qui bloque | via quels LM) ===")
    for t in tensions[:args.top]:
        print(f"\n  {t['gain']:+8.2f}'  {t['name']}")
        for b, r in t["blockers"][:4]:
            via = ', '.join(t["med"].get(b, [])[:3]) or '(pose seule)'
            print(f"      bloque par {b}  (+{r:.2f}')  via: {via}")
        if len(t["blockers"]) > 4:
            print(f"      ... +{len(t['blockers'])-4} bloqueurs")

    print(f"\n=== LEADERBOARD BLOQUEURS (preneurs d'otages) ===")
    for cam_name, (n, g) in sorted(blocker_score.items(), key=lambda x: -x[1][1])[:15]:
        print(f"  bloque {n:3d} deltas, {g:8.1f}' de gain en otage   {cam_name}")

    print(f"\n=== LEADERBOARD LM MEDIATEURS (les charnieres) ===")
    for lm_name, (n, g) in sorted(mediator_score.items(), key=lambda x: -x[1][1])[:15]:
        print(f"  implique dans {n:3d} conflits, ~{g:7.1f}'   {lm_name}")


if __name__ == '__main__':
    main()
