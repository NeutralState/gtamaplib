# Recalibration Workflow

Quick reference: what to do after adding new pixel markings (on leak cams or
calibrated cams) so the whole system stays consistent.

This is the **T3 pipeline in practice**. For the architecture overview see
`CLAUDE_CONTEXT.md` → "T3 Intake Pipeline Complete".

---

## TL;DR — the loop

```
add markings → re-triangulate LMs → recompute tiers
              → (optional) intake new cams
              → bundle adjust → recompute tiers → commit
```

Every step is optional if nothing it touches changed, but in doubt, run them
in order.

---

## Step 0 — What changed?

Before doing anything: **what did you add markings on?**

Three cases, each handled differently:

### Case A — Markings on a LEAK cam

Leak cams have **locked positions** (ground truth). Adding markings to a leak
cam directly improves the triangulation of the LMs it observes — but you must
re-triangulate those LMs so they actually move.

→ Skip to Step 1.

### Case B — Markings on an already-calibrated cam (anchor/high/medium tier)

The cam stays where it is for now, but its observations contribute to the next
bundle adjust. Re-triangulate any LM it observes that has ≥ 2 sources now.

→ Skip to Step 1.

### Case C — Markings on a NEW or low/unverified cam

You're trying to bring this cam into the calibrated set. After re-triangulating
its observed LMs, run `intake_camera.py` to see if it can pass the gate.

→ Skip to Step 1 first, then Step 3.

---

## Step 1 — Re-triangulate affected landmarks

For each LM that now has new observations (or any LM observed by a cam whose
position changed), run:

```bash
python3 tools/triangulate_lm.py "Landmark Name" --apply
```

Or batch (re-triangulates every LM observed by a given cam):

```bash
python3 tools/calibrate_batch.py --retriangulate-only --cam "Some Cam"
```

For everything everywhere (slow, ~minute on full repo):

```bash
python3 tools/calibrate_batch.py --retriangulate-only
```

**Quick sanity check** before moving on:

```bash
python3 tools/triangulate_lm.py "Landmark Name"   # dry run, shows residuals
```

If max residual > 30' the markings have a problem — investigate before
applying.

---

## Step 2 — Recompute tiers

Tiers depend on triangulation quality and source count, so they change after
Step 1.

```bash
python3 tools/compute_confidence_tiers.py
```

Output goes to `tools/generated/confidence_tiers.json`. The terminal summary
shows tier counts; compare against the prior run to see what moved.

This file gates everything downstream — `intake_camera.py` and
`bundle_adjust_weighted.py` both read it.

---

## Step 3 — (Optional, Case C only) Intake new cam

If you just added markings to a new or unverified cam to try to bring it in:

```bash
python3 tools/intake_camera.py "Cam Name"
```

This solves the cam against ONLY anchor+high LMs and reports a verdict:

- **VERDICT: COMMIT** → safe to apply, residuals look good
- **VERDICT: REVIEW** → marginal, look at per-LM table before applying
- **VERDICT: REJECT** → bad markings or insufficient trustworthy coverage

If COMMIT:

```bash
python3 tools/refine_cam_full.py "Cam Name" --apply
```

Then **re-run Step 1** for the LMs this cam now observes, then **re-run
Step 2** to refresh tiers.

If REVIEW: inspect the per-LM residuals printed by intake_camera. Usually
either add more anchor markings or accept and apply manually with
`--force-apply`.

If REJECT: don't apply. The cam isn't ready — needs more markings on
trustworthy LMs first.

---

## Step 4 — Global bundle adjust polish

Once everything's been re-triangulated and any new cams are intaked:

```bash
python3 tools/bundle_adjust_weighted.py
```

This runs tier-weighted global BA over all non-leak cams + LMs. Takes 30s to
2min depending on dataset size.

Reports:
- Initial RMS → final RMS (should drop)
- Largest cam movements (should be small for anchor/high, larger for
  unverified)
- Largest LM movements (similar pattern)

If anything moves more than its tier budget, the soft barrier kicked in (still
allowed, just sub-optimal). That's a signal: the cam/LM might want a different
tier, or there's a marking outlier.

Then apply:

```bash
python3 tools/bundle_adjust_apply.py
```

(type `yes` when prompted)

---

## Step 5 — Recompute tiers (again)

BA changed positions, so tiers might shift. Final refresh:

```bash
python3 tools/compute_confidence_tiers.py
```

Cams with previously-borderline residuals often promote at this stage
(unverified → medium, low → medium, medium → high).

---

## Step 6 — Refresh the dashboard

The dependency graph at `/cam_health.html` reads from cameras.json and the
tiers file. Regenerate it so the new state is visible:

```bash
python3 tools/build_cam_health.py
```

Visit `http://localhost:8765/cam_health.html` to verify.

If you have brand new cams that need thumbnails (i.e. `frames/{Name}.png`
exists but `docs/thumbs/{Name}.jpg` doesn't yet):

```bash
python3 tools/gen_missing_thumbs.py
```

---

## Step 7 — Commit

```bash
cd ~/Downloads/gtamaplib-main && git add gtamapdata/cameras.json gtamapdata/landmarks.json gtamapdata/pixels.json tools/generated/confidence_tiers.json tools/cam_health.html
git status --short
```

Look at what changed before committing. Commit message format:

```
Recalibration <date>: <short summary>

What changed:
- Added markings on: <cam list>
- Re-triangulated: <N> LMs
- Intaked new cams: <list, or "none">
- BA: RMS X → Y (Z% improvement)

Tier diff:
- cams: <before> → <after>
- LMs:  <before> → <after>
```

Then push.

---

## Troubleshooting

### A cam moved way more than its tier budget allows

The soft barrier didn't fully restrain it. Likely causes:
1. **Bad markings** on one of its LMs — check the per-LM residual table from
   `refine_cam_full.py "Cam Name"` (dry run).
2. **An LM that moved a lot** in the same direction (correlation). Check the
   "largest LM movements" list from the BA output.

### Tier dropped (high → medium, etc.) after BA

Means residuals got worse for that cam. Either:
1. The BA found a better global optimum but at this cam's expense — usually OK
   if global RMS dropped.
2. A bad marking is dragging it. Check
   `python3 tools/refine_cam_full.py "Cam Name"` for the per-LM residual
   breakdown.

### `intake_camera.py` says REJECT for a cam I thought was good

Most common cause: **not enough anchor+high LMs in its observations**.
intake_camera ONLY uses anchor+high (the trustworthy skeleton), so if your cam
mostly observes medium/unverified LMs, the gate fails even if the residuals
would be fine.

Fix: add markings on a few anchor LMs (typically Four Seasons towers,
Portofino, or whatever's visible from the cam).

### Container Crane / Sonora Silo / similar outlier kept showing up

These are LMs with chronic triangulation problems (often degenerate observer
geometry). The BA usually resolves them by moving them more than their tier
budget. If a specific LM is consistently the worst residual:

1. Check its `source_cameras` — are they all from one zone with parallel rays?
2. Add a marking from a different angle if possible.
3. Or accept it as a known outlier (LM tier will stay low/unverified, which is
   correct).

### Cam disappeared from the dashboard

The dashboard filters out cams with no edges. If a leak cam has no LM it
sourced, or a calibrated cam has no LM with shared sources, it's filtered.
This is intentional — only "useful" cams (parents of others, or with
trustworthy LMs) show up.

---

## Speed shortcuts

If you know exactly what changed:

**Single new marking on existing cam, LM has 2+ sources:**
```bash
python3 tools/triangulate_lm.py "LM Name" --apply
python3 tools/bundle_adjust_weighted.py
python3 tools/bundle_adjust_apply.py
```

**Just want to test if a cam can be intaked:**
```bash
python3 tools/intake_camera.py "Cam Name"   # dry run, no changes
```

**Just want to see current tier state:**
```bash
python3 tools/compute_confidence_tiers.py 2>&1 | tail -15
```

---

## When NOT to recalibrate

- You added markings but the LM doesn't have ≥ 2 sources yet — wait until it
  does, no useful triangulation possible from 1 source.
- You added markings to a leak cam observing only anchor LMs — anchors are
  already locked, no change happens.
- You added markings during exploration and don't intend to commit — skip the
  whole pipeline.
