#!/usr/bin/env python3
"""ci_healthcheck.py — CI guardrail: runs on every push (GitHub Actions) and
localement avant commit. Exit 1 = le push introduit une regression.

CHECKS:
  1. TIERS      : compute_confidence_tiers.py doit reussir (donnees chargeables)
  2. INVARIANTS : tools/audit/invariants.py (z-constraints, leaks immobiles
                  class-aware, schema, doublons) — exit 1 propage
  3. CYCLES     : circular_deps.py — tout NOUVEAU cycle PUR (auto-referentiel,
                  aucune leak d'ancrage) vs la baseline = FAIL
  4. RMS        : rms_snapshot vs baseline committee — mediane globale qui
                  degrade de plus de TOL_MEDIAN_PCT = FAIL (mean informatif)
  5. JSON       : gtamapdata/*.json parsables + ASCII pur (convention
                  ensure_ascii, evite les diffs parasites)

Baseline: tools/ci_baseline.json (committee). Apres une amelioration legitime:
    python3 tools/ci_healthcheck.py --update-baseline
    git add tools/ci_baseline.json && git commit ...

Usage:
    PYTHONPATH=. python3 tools/ci_healthcheck.py
    PYTHONPATH=. python3 tools/ci_healthcheck.py --update-baseline
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, 'tools', 'ci_baseline.json')
SNAP_PATH = os.path.join(ROOT, 'tools', 'generated', 'rms_snapshot_ci.json')
TOL_MEDIAN_PCT = 10.0     # degradation de mediane globale toleree
PY = sys.executable


def run(cmd, **kw):
    return subprocess.run([PY] + cmd, cwd=ROOT, capture_output=True, text=True,
                          env={**os.environ, 'PYTHONPATH': ROOT}, **kw)


def parse_pure_cycles(stdout):
    """Extrait les ensembles de cams des cycles PURS depuis la sortie de
    circular_deps.py (sections apres '### CYCLES PURS')."""
    cycles = []
    in_pure = False
    for line in stdout.splitlines():
        if 'CYCLES PURS' in line:
            in_pure = True
            continue
        if in_pure and line.startswith('### '):
            in_pure = False
        if in_pure:
            m = re.search(r"SCC \(\d+ cams?\): \[(.*)\]", line)
            if m:
                cams = sorted(re.findall(r"'([^']+)'", m.group(1)))
                cycles.append(cams)
    return sorted(cycles)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--update-baseline', action='store_true')
    args = ap.parse_args()

    fails = []
    print('══ CI HEALTHCHECK ══')

    # ── 1. tiers ──────────────────────────────────────────────────────────
    r = run(['tools/compute_confidence_tiers.py'])
    if r.returncode != 0:
        fails.append('TIERS: compute_confidence_tiers.py a echoue')
        print(r.stdout[-800:], r.stderr[-800:])
    else:
        print('✓ tiers regeneres')

    # ── 2. invariants ────────────────────────────────────────────────────
    r = run(['tools/audit/invariants.py'])
    if r.returncode != 0:
        fails.append('INVARIANTS: violations (voir sortie)')
        print(r.stdout[-1500:])
    else:
        print('✓ invariants OK')

    # ── 2b. ANCHOR-XY: les ancres validees (tooltips) gardent leur xy exact ──
    ref_p = os.path.join(ROOT, 'tools', 'audit', 'anchor_truth_xy.json')
    if os.path.exists(ref_p):
        with open(ref_p) as f:
            ref = json.load(f).get('anchors', {})
        with open(os.path.join(ROOT, 'gtamapdata', 'landmarks.json')) as f:
            lms = json.load(f)
        drift = []
        for k, v in ref.items():
            lm = lms.get(k)
            if not isinstance(lm, dict) or not isinstance(lm.get('xyz'), list):
                continue
            d = ((lm['xyz'][0] - v['xy'][0]) ** 2 + (lm['xyz'][1] - v['xy'][1]) ** 2) ** 0.5
            if d > 0.05:
                drift.append((round(d, 2), k))
        if drift:
            drift.sort(reverse=True)
            fails.append(f'ANCHOR-XY: {len(drift)} ancre(s) validee(s) deplacee(s) '
                         f'(> 0.05 m) — un bundle a fait deriver des tooltips: '
                         + ', '.join(f'{k} {d} m' for d, k in drift[:6]))
        else:
            print(f'✓ ancres xy: {len(ref)} ancres validees a leur valeur de reference')

    # ── 3. cycles purs ───────────────────────────────────────────────────
    r = run(['tools/audit/circular_deps.py'])
    pure = parse_pure_cycles(r.stdout)
    print(f'  cycles purs actuels: {len(pure)}')

    # ── 4. rms snapshot ──────────────────────────────────────────────────
    r = run(['tools/audit/rms_snapshot.py', '--tag', 'ci'])
    summary = None
    if r.returncode != 0 or not os.path.exists(SNAP_PATH):
        fails.append('RMS: rms_snapshot a echoue')
    else:
        with open(SNAP_PATH) as f:
            summary = json.load(f)['summary']
        print(f"  mediane globale: {summary['global_median_arcmin']}'  "
              f"mean: {summary['global_mean_arcmin']}'  "
              f"median_m: {summary.get('global_median_m')}m")

    # ── 5. json hygiene ──────────────────────────────────────────────────
    for p in sorted(glob.glob(os.path.join(ROOT, 'gtamapdata', '*.json'))):
        try:
            raw = open(p, 'rb').read()
            json.loads(raw)
            if any(b > 127 for b in raw):
                fails.append(f'JSON: {os.path.basename(p)} contient du non-ASCII '
                             '(convention ensure_ascii=True)')
        except Exception as e:
            fails.append(f'JSON: {os.path.basename(p)} invalide: {e}')
    if not any(f_.startswith('JSON') for f_ in fails):
        print('✓ json hygiene OK')

    # ── 6. fossil scan (WARNING only, never fails) [FOSSIL-SCAN-V1] ─────
    # LMs whose own source cams reject them = stale xyz from an old pose.
    try:
        from common import find_fossils
        fossils = find_fossils()
        if fossils:
            print(f'⚠ fossils: {len(fossils)} LM(s) rejected by their own source')
            for x in fossils[:5]:
                r = f"{x['resid']}'" if x['resid'] is not None else 'no-proj'
                print(f"    {r:>9s}  {x['lm']}  (source: {x['source']})")
            if len(fossils) > 5:
                print(f'    ... +{len(fossils)-5} more (see Triage board)')
        else:
            print('✓ fossils: none')
        # ── WAR-SCAN light (WARNING only) [WAR-CI-V1, 2026-07-08] ──────
        # Compte les LM avec >=1 observer en outlier DUAL (ang>15' ET
        # gap>3m) — version legere du collision_scan pour le CI.
        try:
            from common import get_cam, residual_dual, is_excluded_marking
            import gtamapdata as _md
            war_lms = set()
            for _c, _obs in _md.pixels.items():
                _cam = get_cam(_c)
                if _cam is None:
                    continue
                for _l, _px in _obs.items():
                    if _px is None or is_excluded_marking(_c, _l):
                        continue
                    _xyz = _md.landmarks.get(_l)
                    if _xyz is None:
                        continue
                    _a, _g, _d = residual_dual(_cam, _px, _xyz)
                    if _a is not None and _a > 15 and (_g is None or _g > 3.0):
                        war_lms.add(_l)
            if war_lms:
                print(f'⚠ wars: {len(war_lms)} LM avec outlier dual '
                      f'(collision_scan pour le detail)')
            else:
                print('✓ wars: aucun outlier dual')
        except Exception as _e:
            print(f'  (war-scan light indisponible: {_e})')
    except Exception as e:
        print(f'⚠ fossil scan failed: {e}')

    # ── 7. orphan scan (WARNING) [ORPHAN-SCAN-V1] ────────────────────────
    # LM with xyz whose NO source cam still has a marking on it: the fossil
    # detector's documented blind spot (e.g. after renaming markings).
    try:
        import gtamapdata as _md
        orphans = []
        for _lm, _xyz in _md.landmarks.items():
            if _xyz is None:
                continue
            _src = (_md.landmarks_meta.get(_lm) or {}).get('source_cameras', []) or []
            # empty sources = derived/procedural LM (rigid bodies, mast levels,
            # z-constraint solves) — legitimate. Orphan = sources LISTED but
            # none of them still has a marking (e.g. after a rename).
            _real = [_c for _c in _src if not str(_c).startswith('(legacy')]
            if _real and not any(_md.pixels.get(_c, {}).get(_lm) is not None for _c in _real):
                orphans.append(_lm)
        if orphans:
            print(f'⚠ orphans: {len(orphans)} LM(s) with xyz but no source marking left')
            for _o in orphans[:5]:
                print(f'      {_o}')
            if len(orphans) > 5:
                print(f'      ... +{len(orphans)-5} more')
        else:
            print('✓ orphans: none')
    except Exception as e:
        print(f'⚠ orphan scan failed: {e}')

    # ── baseline ─────────────────────────────────────────────────────────
    if args.update_baseline:
        if summary is None:
            print('FAIL: impossible de geler une baseline sans snapshot valide')
            return 1
        with open(BASELINE, 'w') as f:
            json.dump({'global_median_arcmin': summary['global_median_arcmin'],
                       'global_mean_arcmin': summary['global_mean_arcmin'],
                       'global_median_m': summary.get('global_median_m'),
                       'pure_cycles': pure}, f, indent=1, sort_keys=True)
            f.write('\n')
        print(f'BASELINE GELEE -> {BASELINE} (a committer)')
        return 0

    if not os.path.exists(BASELINE):
        fails.append('BASELINE: tools/ci_baseline.json absent — roule '
                     '--update-baseline une premiere fois et committe-le')
    elif summary is not None:
        with open(BASELINE) as f:
            base = json.load(f)
        # cycles: tout nouveau cycle pur = fail
        known = [tuple(c) for c in base.get('pure_cycles', [])]
        new_cycles = [c for c in pure if tuple(c) not in known]
        if new_cycles:
            fails.append(f'CYCLES: {len(new_cycles)} NOUVEAU(X) cycle(s) PUR(S) '
                         f'(auto-referentiels, aucune leak): {new_cycles}')
        else:
            print(f'✓ cycles purs: aucun nouveau (baseline: {len(known)})')
        # mediane
        bm = base['global_median_arcmin']
        cm = summary['global_median_arcmin']
        if bm > 0 and (cm - bm) / bm * 100 > TOL_MEDIAN_PCT:
            fails.append(f'RMS: mediane globale degradee {bm}\' -> {cm}\' '
                         f'(> {TOL_MEDIAN_PCT}% tolere)')
        else:
            print(f'✓ mediane vs baseline: {bm}\' -> {cm}\'')
        # DUAL-METRIC-V1: mediane metres — tolerant si baseline ancienne
        bm_m = base.get('global_median_m')
        cm_m = summary.get('global_median_m')
        if bm_m is not None and cm_m is not None:
            # tolerance plancher (lecon 0708): la mediane sur 119 cams bouge
            # par pas discrets — un switch de point median de 0.02m = 12% a
            # 0.17m sans vraie regression. Fail seulement au-dela de
            # max(TOL%, 0.03m absolu).
            tol_abs = max(bm_m * TOL_MEDIAN_PCT / 100.0, 0.03)
            if bm_m > 0 and (cm_m - bm_m) > tol_abs:
                fails.append(f'RMS-M: mediane metres degradee {bm_m}m -> {cm_m}m '
                             f'(> max({TOL_MEDIAN_PCT}%, 0.03m) tolere)')
            else:
                print(f'✓ mediane metres vs baseline: {bm_m}m -> {cm_m}m')
        elif cm_m is not None:
            print(f'  mediane metres: {cm_m}m (baseline ancienne sans metres — '
                  f'--update-baseline pour geler)')

    print()
    if fails:
        print(f'HEALTHCHECK: {len(fails)} ECHEC(S)')
        for f_ in fails:
            print('  FAIL', f_)
        return 1
    print('HEALTHCHECK OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
