# Recalibration Workflow (V2)

Quick reference: what to do after adding new pixel markings (on leak cams,
community cams, or anything else) so the whole system stays consistent.

This is the **T3 pipeline in practice**, updated for the V2 constraint-class
system. For the architecture overview see `CLAUDE_CONTEXT.md` and
`V2_CONSTRAINT_CLASSES.md`.

---

## Outils d'audit READ-ONLY (tools/audit/) — sante du reseau

Ces outils ne modifient RIEN. A lancer periodiquement (surtout apres un gros
batch de retriangulation/recalibration) pour verifier la sante globale, pas
juste un LM a la fois.

### `retriangulation_candidates.py` (Chantier A)
Scanne tous les LM, rejoue la selection de sources + triangulation, classe par
GAIN potentiel (parallaxe >=15deg, delta >=2m, >=2 sources post-dedup).
→ Quand: pour savoir QUELS LM beneficieraient d'une retriangulation avant de se
  lancer. Sortie taggee CAND / NEAR / NOBASE / SKIP.

### `circular_deps.py` (Chantier B)
Construit le graphe de dependance cam->cam (B-strict) + Tarjan SCC. Detecte les
CYCLES: groupes de cams qui se valident mutuellement sans ancrage leak (PUR =
suspect auto-referentiel, SAIN = ancre par une leak dans la boucle).
→ Quand: apres avoir ajoute/recalibre des cams, pour s'assurer qu'on n'a pas
  cree de zone auto-referentielle. `--dump-graph` pour le graphe complet.
→ Connu (2026-06): 3 cycles purs = Ambrosia, Port Gellhorn, Chase2.

### `lm_uncertainty.py` (Chantier C1)
Incertitude 3D par LM via Monte-Carlo (perturbe pixels + poses, retriangule N
fois, covariance du nuage). Sortie: r_pose (incertitude totale), r_pix (bruit
pixel seul), ratio = r_pose/r_pix.
→ Lecture: ratio ~1 = fragilite PHYSIQUE (point lointain, irreparable);
  ratio >2 = fragilite REPARABLE (poses sources fragiles -> reancrer).
→ Insight cle: le RMS ne mesure PAS l'incertitude. Un LM peut avoir un residu
  parfait et etre incertain de 100m+. Cet outil voit ce que le RMS cache.
→ Quand: pour prioriser quels LM/cams ont besoin d'une 3e source ou d'un reancrage.
  ~3min pour 382 LM a N=200.

### `audit_leak_influence_tree.py`
Arbre d'influence descendante depuis chaque leak cam (quelle leak influence le
plus de LM/cams en aval). → Quand: pour prioriser quelle leak calibrer en premier.

---

## TL;DR — the loop

```
add markings → re-triangulate LMs → recompute tiers
              → (optional) refine / intake new cams
              → bundle adjust → recompute tiers → commit
```

Every step is optional if nothing it touches changed, but when in doubt, run
them in order.

---

## Step 0 — Know your cam's class

Before doing anything, check what kind of cam you just touched. The V2
audit assigns each cam a `constraint_class` that decides which DOF can be
refined.

```bash
python3 tools/leak_cam_audit.py "Cam Name"
```

That prints the class and what's locked vs refinable. Quick reference:

| Class                    | Locked DOF       | Refinable DOF   | Right tool             |
|--------------------------|------------------|-----------------|------------------------|
| `A_full_hud`             | xyz, ypr, fov    | — (anchor)      | none                   |
| `B_pos_fov_player`       | xyz, fov         | ypr (roll prior)| `refine_cam_ypr.py`    |
| `C_pos_fov_only`         | xyz, fov         | ypr             | `refine_cam_ypr.py`    |
| `Cm_pos_only`            | xyz              | ypr, fov        | `refine_cam_full.py`   |
| `D_no_ground_truth`      | (none)           | xyz, ypr, fov   | `refine_cam_full.py`   |
| `X_invalid_ground_truth` | excluded         | —               | none                   |
| `_legacy_date` (synthetic)| xyz, ypr, fov   | — (anchor)      | none                   |
| no audit entry           | (none)           | xyz, ypr, fov   | `refine_cam_full.py`   |

For the rare case where you need to override the gate (e.g. re-calibrate a
class A cam after correcting its audit entry), pass `--ignore-class` to the
relevant tool.

### Don't want to think about it?

Use the dispatcher:

```bash
python3 -c "
import sys; sys.path.insert(0, 'tools')
from calibrate_batch import _refine_tool_for
print(_refine_tool_for('Your Cam Name'))
"
```

It returns the right tool path and the reasoning.

---

## Step 0.5 — What case are you in?

Three cases, each routed differently:

### Case A — Markings on an A or `_legacy_date` cam

These have **all DOF locked** (HUD ground truth). Adding markings to one of
them directly improves the triangulation of the LMs it observes — but you
must re-triangulate those LMs so they actually move.

→ Skip refine, go straight to Step 1.

### Case B — Markings on a B / C / Cm cam (xyz locked)

These have **HUD-locked xyz** but their ypr (and fov for Cm) was solver-
derived. New markings can both improve LM triangulation AND refine the cam's
own ypr/fov.

→ Step 1 (re-triangulate), then Step 3a (refine the cam), then Step 2.

### Case C — Markings on a D / non-audit / community cam

These have **nothing locked**. They behave like any community-calibrated cam.

→ Step 1, then Step 3 (intake or refine), then Step 2.

### Case D — Markings on an X cam

Don't. Class X is excluded from every pipeline step. If you think the cam is
recoverable, audit it first to reclassify it.

---

## Step 1 — Re-triangulate affected landmarks

For each LM that has new observations (or any LM observed by a cam whose
position changed), run:

```bash
python3 tools/triangulate_lm.py "Landmark Name" --apply
```

To batch-retriangulate every LM observed by a cam you just refined, loop
over them manually (the tool takes one LM at a time):

```bash
python3 -c "
import json
pixels = json.load(open('gtamapdata/pixels.json'))
for lm in pixels.get('Cam Name You Refined', {}):
    print(lm)
" | while read lm; do
    python3 tools/triangulate_lm.py "$lm" --apply
done
```

(The cam's observations are in `pixels.json[cam_name]` as `{lm_name: [px, py]}`.
The loop runs `triangulate_lm.py` for each one.)

**Quick sanity check** before applying:

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

## Step 3 — Refine or intake the cam (Cases B and C)

### Step 3a — Refine an already-calibrated cam (Case B mostly)

If the cam already has a calibration and you just want to nudge it with the
new markings, use the right refine tool for its class:

```bash
# Class B or C: ypr-only refinement (xyz and fov stay HUD-locked)
python3 tools/refine_cam_ypr.py "Cam Name"            # dry run
python3 tools/refine_cam_ypr.py "Cam Name" --apply    # commit

# Class Cm: joint ypr+fov refinement (xyz auto-locked)
python3 tools/refine_cam_full.py "Cam Name"           # dry run
python3 tools/refine_cam_full.py "Cam Name" --apply   # commit

# Class D / community cam: full xyz+ypr+fov solve
python3 tools/refine_cam_full.py "Cam Name"           # dry run
python3 tools/refine_cam_full.py "Cam Name" --apply   # commit
```

For class B (a player ped is visible in the frame), `refine_cam_ypr` adds
a soft roll prior (sigma=2°) to keep roll near 0° — the ped's vertical pose
anchors it.

### Step 3b — Intake a NEW cam (Case C)

If you just added markings to a new or unverified cam to try to bring it in:

```bash
python3 tools/intake_camera.py "Cam Name"
```

This solves the cam against ONLY anchor+high LMs and reports a verdict:

- **VERDICT: COMMIT** → safe to apply, residuals look good
- **VERDICT: REVIEW** → marginal, look at per-LM table before applying
- **VERDICT: REJECT** → bad markings or insufficient trustworthy coverage

For class B/C/Cm cams, `intake_camera.py` auto-sets the right DOF flags
(`--no-hfov` on B/C, fov unlocked on Cm).

If COMMIT:

```bash
python3 tools/refine_cam_full.py "Cam Name" --apply   # or refine_cam_ypr per class
```

Then re-run Step 1 for the LMs this cam now observes, then re-run Step 2 to
refresh tiers.

If REVIEW: inspect the per-LM residuals printed by `intake_camera`. Usually
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

This runs tier-weighted global BA over all non-xyz-locked cams + LMs. Takes
30s to 2min depending on dataset size.

V2: cams with `constraint_class` in {A, B, C, Cm, _legacy_date} are excluded
from the BA parameter vector (their xyz/ypr/fov are taken as ground truth or
already refined). Class D and non-audit cams ARE in the param vector and can
move.

Reports:
- Initial RMS → final RMS (should drop)
- Largest cam movements (should be small for anchor/high, larger for
  unverified)
- Largest LM movements (similar pattern)

If anything moves more than its tier budget, the soft barrier kicked in
(still allowed, just sub-optimal). That's a signal: the cam/LM might want
a different tier, or there's a marking outlier.

Then apply — **via le guarded apply UNIQUEMENT** (doctrine 2026-07-01):

```bash
python3 tools/refine/guarded_apply.py            # dry-run: lire la liste des deltas
python3 tools/refine/guarded_apply.py --apply    # applique seulement ce qui ameliore
python3 tools/audit/rms_snapshot.py --tag apres_<nom>
```

Le guarded evalue chaque delta individuellement contre les residuels bruts et
rejette tout ce qui degrade quoi que ce soit (tol 0.25').

> **INTERDIT**: `bundle_adjust_apply.py` (apply integral aveugle) — retire de
> la doctrine le 2026-07-01. L'apply integral d'un resultat de bundle a cause
> les regressions historiques (Pool/Motel). Toujours: bundle --cleanup ->
> guarded dry -> guarded --apply -> snapshot. Le flag `--cleanup` est
> obligatoire (exclut junk cams, weak LMs, triangulations cassees; garde les
> rays leak-anchored comme ancres).
>
> Option `--continuous`: poids LM continus 1/sigma depuis lm_uncertainty
> (A/B 2026-07-02: harvest identique aux buckets sur l'etat courant — le
> guarded est robuste au schema de ponderation; utile potentiellement dans
> les clusters contestes).

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
- Intaked / refined new cams: <list, or "none">
- BA: RMS X → Y (Z% improvement)

Tier diff:
- cams: <before> → <after>
- LMs:  <before> → <after>
```

Then push.

---

## Troubleshooting

### "ERROR: 'Cam Name' is class A_full_hud — already locked"

You tried to refine an anchor cam. Either:
1. The cam is correctly classified — don't refine it, it's ground truth.
2. The cam was misclassified — fix `leak_cam_audit.json` and re-run
   `migrate_constraint_classes.py --apply --overwrite-a`.

### "ERROR: '...' is class Cm_pos_only — fov is not ground-truth"

`refine_cam_ypr.py` refuses class Cm because fov needs to be refined too.
Switch to `refine_cam_full.py` which auto-locks xyz and refines ypr+fov.

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
`intake_camera` ONLY uses anchor+high (the trustworthy skeleton), so if your
cam mostly observes medium/unverified LMs, the gate fails even if the
residuals would be fine.

Fix: add markings on a few anchor LMs (typically Four Seasons towers,
Portofino, or whatever's visible from the cam).

### "Legacy date-source cam without audit entry"

Three known cams fall through here: `Hedge (B) (X)`, `Hedge (C) (X)`,
`Grassrivers Sign`. They have `YYYY-MM-DD` in their source field but no
`leak_cam_audit.json` entry. The helper treats them as `_legacy_date` (fully
locked, V1-equivalent) for safety.

To clear the warning, add explicit `constraint_class` entries for them in
`leak_cam_audit.json`, then run `migrate_constraint_classes.py --apply`.

### Container Crane / Sonora Silo / similar outlier kept showing up

These are LMs with chronic triangulation problems (often degenerate observer
geometry). The BA usually resolves them by moving them more than their tier
budget. If a specific LM is consistently the worst residual:

1. Check its `source_cameras` — are they all from one zone with parallel rays?
2. Add a marking from a different angle if possible.
3. Or accept it as a known outlier (LM tier will stay low/unverified, which
   is correct).

### Cam disappeared from the dashboard

The dashboard filters out cams with no edges. If an xyz-locked cam has no LM
it sourced, or a community cam has no LM with shared sources, it's filtered.
This is intentional — only "useful" cams (parents of others, or with
trustworthy LMs) show up.

---

## Speed shortcuts

If you know exactly what changed:

**Single new marking on existing cam, LM has 2+ sources:**
```bash
python3 tools/triangulate_lm.py "LM Name" --apply
python3 tools/bundle_adjust_weighted.py --cleanup
python3 tools/refine/guarded_apply.py --apply
```

**Just want to test if a cam can be intaked:**
```bash
python3 tools/intake_camera.py "Cam Name"   # dry run, no changes
```

**Just want to see current tier state:**
```bash
python3 tools/compute_confidence_tiers.py 2>&1 | tail -15
```

**Just want to see a cam's V2 class:**
```bash
python3 tools/leak_cam_audit.py "Cam Name"
```

**Don't know which refine tool to use:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'tools')
from calibrate_batch import _refine_tool_for
print(_refine_tool_for('Cam Name'))
"
```

---

## When NOT to recalibrate

- You added markings but the LM doesn't have ≥ 2 sources yet — wait until it
  does, no useful triangulation possible from 1 source.
- You added markings on a class A cam observing only anchor LMs — both are
  already locked, no change happens.
- You added markings during exploration and don't intend to commit — skip the
  whole pipeline.

---

## V2 quick reference card

```
Audit classes (count in current cameras.json):
  A_full_hud         13   xyz+ypr+fov locked (anchor)
  B_pos_fov_player    5   xyz+fov locked, ypr free (with roll prior)
  C_pos_fov_only     61   xyz+fov locked, ypr free
  Cm_pos_only         2   xyz locked, ypr+fov free
  D_no_ground_truth   9   nothing locked, full solve
  X_invalid           0   excluded
  _legacy_date        3   xyz+ypr+fov locked (synthetic fallback)
  no audit entry     78   nothing locked, full solve

Total: 171 cams, 84 with HUD-locked xyz
```

Refine tool routing summary:

```
class A     → no tool (anchor, refuse)
class B/C   → refine_cam_ypr.py
class Cm    → refine_cam_full.py (auto-locks xyz via --fix-xy)
class D     → refine_cam_full.py
no audit    → refine_cam_full.py
class X     → no tool (excluded)
_legacy_date → no tool (treated as anchor)
```
