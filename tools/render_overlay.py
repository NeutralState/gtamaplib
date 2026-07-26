#!/usr/bin/env python3
"""render_overlay.py — la carte projetee DANS la frame. [OVERLAY-V1]

Meme idee que l'overlay de rlx sur Ambrosia (meshs + lignes de fuite +
labels verticaux), mais en exploitant ce que nos donnees ont en plus:

  * PREDIT vs OBSERVE: pour chaque clic de la cam, on dessine ou la carte
    place le landmark (cercle) ET ou le clic est (croix), relies par un
    vecteur colore par l'erreur (vert <5', ambre <15', rouge au-dela).
    L'overlay devient un instrument de diagnostic, pas juste un decor.
  * INCERTITUDE: error_m de chaque landmark projete en pixels -> moustache
    horizontale sous le point. On VOIT quels points sont mous.
  * MESHS: les world_edges de building_meshes_procedural.json (silo, WDNA,
    Vizcayne...) projetes avec leur couleur.
  * GRATICULE VRAI: horizon reel (elevation 0, roll compris) + meridiens
    de bearing tous les 5 deg, labels compas tous les 15.
  * CAMS: frustums des autres cameras dans le champ, nom + distance.
  * POLYLINES SOL: rive du lac Leonida, Main St (GROUND-V1).
  * SUGGESTIONS: landmarks places mais non marques dans cette cam ->
    losange creux discret (ce qu'il reste a marquer).

Marche pour N'IMPORTE quelle cam posee: --cam 'Nom' [--cam 'Autre' ...]
Sortie: tools/generated/overlays/<cam>.png ; --no-frame pour fond noir.
"""
import argparse
import collections
import json
import math
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import common

MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')

# familles de points-sol relies en polyline (ordre = suffixe lettre)
POLYLINES = [
    ('Lake Leonida (',      '#7dd3fc', 'lake shoreline'),
    ('Ambrosia Main St (',  '#fbbf24', 'Main St'),
]

C_OK, C_WARN, C_BAD = '#4ade80', '#fbbf24', '#f87171'
C_GRAT = (250, 204, 21)          # graticule jaune, alpha module
C_SUGG = '#94a3b8'
C_EXCL = '#64748b'
C_CAM = '#f472b6'


def err_color(arcmin):
    return C_OK if arcmin < 5 else (C_WARN if arcmin < 15 else C_BAD)


def bearing_dir(b_deg, el_deg):
    """Direction monde pour bearing compas (atan2(est, nord)) + elevation."""
    b, e = math.radians(b_deg), math.radians(el_deg)
    return np.array([math.sin(b) * math.cos(e), math.cos(b) * math.cos(e), math.sin(e)])


class View:
    def __init__(self, cam_name):
        self.cam = common.get_cam(cam_name)
        self.o = np.asarray(self.cam.xyz, float)
        self.w, self.h = self.cam.w, self.cam.h
        self.focal_px = self.w / (2 * math.tan(math.radians(self.cam.hfov) / 2))

    def px(self, P):
        p = self.cam.get_pixel([float(v) for v in P])
        return None if p is None else (float(p[0]), float(p[1]))

    def px_dir(self, d, dist=20000.0):
        return self.px(self.o + dist * np.asarray(d, float))

    def in_frame(self, p, margin=0):
        return (p is not None and -margin <= p[0] < self.w + margin
                and -margin <= p[1] < self.h + margin)

    def polyline_px(self, world_pts, samples=6):
        """Projette une polyline monde en segments pixel, coupee quand un
        point passe derriere la cam ou sort tres loin du cadre."""
        segs, cur = [], []
        for i in range(len(world_pts) - 1):
            A = np.asarray(world_pts[i], float)
            B = np.asarray(world_pts[i + 1], float)
            for t in np.linspace(0, 1, samples):
                p = self.px(A + t * (B - A))
                if p is None or abs(p[0]) > 4 * self.w or abs(p[1]) > 4 * self.h:
                    if len(cur) > 1:
                        segs.append(cur)
                    cur = []
                else:
                    cur.append(p)
        if len(cur) > 1:
            segs.append(cur)
        return segs


def rot_label(base, x, y, text, fill, font, stroke='#0b0f14', gap=10):
    """Label vertical (lecture de bas en haut) au-dessus de (x, y)."""
    d0 = ImageDraw.Draw(base)
    bb = d0.textbbox((0, 0), text, font=font, stroke_width=2)
    tw, th = bb[2] - bb[0] + 4, bb[3] - bb[1] + 6
    tile = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((2, 2 - bb[1]), text, fill=fill, font=font,
                              stroke_width=2, stroke_fill=stroke)
    tile = tile.rotate(90, expand=True)
    base.alpha_composite(tile, (int(x - tile.width // 2), int(y - gap - tile.height)))


def load_data():
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    meshes = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    return px, lms, cams, meshes


def render(cam_name, px, lms, cams, meshes, args):
    v = View(cam_name)
    frame_path = os.path.join(REPO, 'frames', f'{cam_name}.png')
    if not args.no_frame and os.path.exists(frame_path):
        img = Image.open(frame_path).convert('RGB').resize((v.w, v.h))
        img = Image.blend(img, Image.new('RGB', img.size, (6, 9, 14)), args.dim)
    else:
        img = Image.new('RGB', (v.w, v.h), (6, 9, 14))
    img = img.convert('RGBA')
    ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
    do = ImageDraw.Draw(ov)

    try:
        F = lambda s: ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', s)
        f_lab, f_sm, f_hdr = F(26), F(22), F(30)
    except Exception:
        f_lab = f_sm = f_hdr = ImageFont.load_default()

    # ── 1. graticule: meridiens de bearing + horizon vrai ───────────────
    ticks = []
    for b in range(0, 360, args.grat_step):
        pts = [v.px_dir(bearing_dir(b, e)) for e in np.arange(-38, 38.1, 2.0)]
        pts = [p for p in pts if p is not None and -v.w < p[0] < 2 * v.w]
        if len(pts) < 2:
            continue
        major = (b % 15 == 0)
        do.line(pts, fill=C_GRAT + ((46,) if major else (20,)), width=2 if major else 1)
        hz = v.px_dir(bearing_dir(b, 0.0))
        if major and v.in_frame(hz, margin=30):
            ticks.append((b, hz))
    hz_pts = [v.px_dir(bearing_dir(b, 0.0)) for b in np.arange(0, 360, 0.5)]
    hz_pts = [p for p in hz_pts if p is not None and -v.w < p[0] < 2 * v.w]
    hz_pts.sort(key=lambda p: p[0])
    if len(hz_pts) > 1:
        do.line(hz_pts, fill=C_GRAT + (70,), width=2)
    for b, hz in ticks:
        do.line([hz[0], hz[1] - 10, hz[0], hz[1] + 10], fill=C_GRAT + (150,), width=3)
        do.text((hz[0] + 6, hz[1] + 10), f'{b:03d}°', fill=C_GRAT + (170,), font=f_sm,
                stroke_width=2, stroke_fill=(6, 9, 14, 200))

    # ── 2. meshs ────────────────────────────────────────────────────────
    for name, m in meshes.items():
        edges = m.get('world_edges') or []
        col = m.get('color', '#60a5fa')
        drawn, samp = 0, []
        for a, b in edges:
            pa, pb = v.px(a), v.px(b)
            if pa is None or pb is None:
                continue
            if not (v.in_frame(pa, 200) or v.in_frame(pb, 200)):
                continue
            do.line([pa, pb], fill=col, width=2)
            samp.append(pa)
            drawn += 1
        if drawn > 4 and args.mesh_labels:
            cx = min(s[0] for s in samp)
            cy = min(s[1] for s in samp)
            dist = np.linalg.norm(np.mean([e[0] for e in edges], axis=0) - v.o)
            do.text((cx, cy - 30), f'{name}  {dist:.0f} m', fill=col, font=f_sm,
                    stroke_width=2, stroke_fill=(6, 9, 14, 220))

    # ── 3. polylines sol ────────────────────────────────────────────────
    for prefix, col, lab in POLYLINES:
        fam = sorted((k, e) for k, e in lms.items()
                     if k.startswith(prefix) and isinstance(e, dict) and e.get('xyz')
                     and 'dup' not in (e.get('note') or ''))
        pts = [e['xyz'] for _, e in fam]
        if len(pts) < 2:
            continue
        first = True
        for seg in v.polyline_px(pts):
            do.line(seg, fill=col, width=3)
            if first and v.in_frame(seg[0], 0):
                do.text((seg[0][0] + 8, seg[0][1] + 8), lab, fill=col, font=f_sm,
                        stroke_width=2, stroke_fill=(6, 9, 14, 220))
                first = False

    # ── 4. frustums des autres cams ─────────────────────────────────────
    labels = []          # (x_pixel, priorite, texte, couleur, y_anchor)
    for cn, ce in cams.items():
        if cn == cam_name or not (ce.get('xyz') and ce.get('ypr')
                                  and ce.get('fov') and ce['fov'][0]):
            continue
        C = np.asarray(ce['xyz'], float)
        pc = v.px(C)
        if not v.in_frame(pc, 60):
            continue
        dist = float(np.linalg.norm(C - v.o))
        oc = common.get_cam(cn)              # gotcha #5: instance partagee
        corners = [np.asarray(oc.get_pixel_direction((x, y)), float)
                   for x, y in ((0, 0), (oc.w, 0), (oc.w, oc.h), (0, oc.h))]
        L = max(20.0, dist * 0.012)
        cp = [v.px(C + L * (d / np.linalg.norm(d))) for d in corners]
        for i in range(4):
            if cp[i] is not None:
                do.line([pc, cp[i]], fill=C_CAM, width=2)
            if cp[i] is not None and cp[(i + 1) % 4] is not None:
                do.line([cp[i], cp[(i + 1) % 4]], fill=C_CAM, width=2)
        do.ellipse([pc[0] - 6, pc[1] - 6, pc[0] + 6, pc[1] + 6], fill=C_CAM)
        # priorite negative: les cams gagnent toujours leur label
        labels.append((pc[0], dist - 1e6, f'{cn}  {dist:.0f} m', C_CAM, pc[1]))

    # ── 5. landmarks: predit vs observe + moustaches + suggestions ──────
    marks = px.get(cam_name) or {}

    # --xval: le point predit devient la triangulation SANS cette cam
    # (hors-echantillon, crossval.py visualise) quand >= 2 autres vues
    loo = {}
    if args.xval:
        obs_of = collections.defaultdict(list)
        for c2, mk in px.items():
            if c2 == cam_name or c2 not in cams:
                continue
            ce2 = cams[c2]
            if not (ce2.get('xyz') and ce2.get('ypr') and ce2.get('fov')
                    and ce2['fov'][0]):
                continue
            for lm2, p2 in mk.items():
                if p2 is not None and not common.is_excluded_marking(c2, lm2):
                    obs_of[lm2].append((c2, p2))
        for lm2 in marks:
            if len(obs_of.get(lm2, ())) < 2:
                continue
            rays = []
            for c2, p2 in obs_of[lm2]:
                oc2 = common.get_cam(c2)
                d2 = np.asarray(oc2.get_pixel_direction(p2), float)
                rays.append((np.asarray(oc2.xyz, float), d2 / np.linalg.norm(d2)))
            try:
                P2 = np.asarray(common.ray_ls_point(rays), float)
                if np.all(np.isfinite(P2)) and max(abs(x) for x in P2) < 1e6:
                    loo[lm2] = P2
            except Exception:
                pass
    n_ok = n_warn = n_bad = 0
    errs = []
    for lm, e in lms.items():
        if not isinstance(e, dict) or not e.get('xyz'):
            continue
        P = np.asarray(loo.get(lm, e['xyz']), float)
        pp = v.px(P)
        if pp is None:
            continue
        dist = float(np.linalg.norm(P - v.o))
        obs = marks.get(lm)
        excl = common.is_excluded_marking(cam_name, lm)

        if obs is not None:
            # vecteur d'erreur predit <-> observe
            dx = (pp[0] - obs[0]) * v.cam.hfov / v.w * 60.0
            dy = (pp[1] - obs[1]) * v.cam.vfov / v.h * 60.0
            am = math.hypot(dx, dy)
            col = C_EXCL if excl else err_color(am)
            if not excl:
                errs.append(am)
                n_ok += am < 5; n_warn += 5 <= am < 15; n_bad += am >= 15
            if not (v.in_frame(pp, 100) or v.in_frame(obs, 100)):
                continue
            do.line([obs[0] - 8, obs[1] - 8, obs[0] + 8, obs[1] + 8], fill=col, width=3)
            do.line([obs[0] - 8, obs[1] + 8, obs[0] + 8, obs[1] - 8], fill=col, width=3)
            do.ellipse([pp[0] - 7, pp[1] - 7, pp[0] + 7, pp[1] + 7], outline=col, width=3)
            if math.hypot(pp[0] - obs[0], pp[1] - obs[1]) > 12:
                do.line([obs, pp], fill=col, width=2)
                if am >= 5:
                    do.text((pp[0] + 10, pp[1] - 4), f"{am:.0f}'", fill=col, font=f_sm,
                            stroke_width=2, stroke_fill=(6, 9, 14, 220))
            # moustache d'incertitude (error_m projete)
            err_m = e.get('error_m')
            if err_m and dist > 1:
                half = err_m / dist * v.focal_px
                if 4 < half < v.w:
                    do.line([pp[0] - half, pp[1] + 14, pp[0] + half, pp[1] + 14],
                            fill=col + 'aa' if isinstance(col, str) else col, width=3)
            labels.append((pp[0], dist, f'{lm}  {dist:.0f} m', col, min(pp[1], obs[1])))
        elif v.in_frame(pp, 0) and dist < args.sugg_dist and not args.no_suggest:
            # place mais non marque ici: ce qu'il reste a marquer
            do.polygon([pp[0], pp[1] - 8, pp[0] + 8, pp[1], pp[0], pp[1] + 8,
                        pp[0] - 8, pp[1]], outline=C_SUGG, width=2)
            labels.append((pp[0], dist + 1e6, f'{lm}  {dist:.0f} m', C_SUGG, pp[1]))

    # labels: anti-collision sur deux etages (priorite: cams, puis proches)
    bands = ([], [])
    placed = []
    for x, pr, txt, col, y in sorted(labels, key=lambda t: t[1]):
        free = [b for b in (0, 1) if all(abs(x - u) >= args.label_gap for u in bands[b])]
        if not free:
            continue
        b = free[0]
        bands[b].append(x)
        placed.append(x)
        rot_label(ov, x, y, txt, col, f_lab, gap=10 + b * 150)

    # ── 6. header minimal (1 ligne) ─────────────────────────────────────
    rms = common.cam_rms(cam_name)
    st = cams[cam_name]
    hdr = (f'{cam_name}   xyz ({st["xyz"][0]:.0f}, {st["xyz"][1]:.0f}, {st["xyz"][2]:.1f})   '
           f'yaw {st["ypr"][0]:.1f}  pitch {st["ypr"][1]:.1f}  hfov {st["fov"][0]:.1f}   '
           f'{len([1 for m in marks.values() if m])} marks   rms {rms:.1f}\''
           if rms else cam_name)
    do.text((24, 18), hdr, fill='#e2e8f0', font=f_hdr, stroke_width=3,
            stroke_fill=(6, 9, 14, 230))
    if errs:
        mode = ('prediction HORS-ECHANTILLON (triangulee sans cette cam)'
                if args.xval else 'residu map->frame')
        leg = (f"{mode}:  {n_ok} sous 5'   {n_warn} entre 5-15'   "
               f"{n_bad} au-dela   (mediane {np.median(errs):.1f}')")
        do.text((24, 58), leg, fill='#94a3b8', font=f_sm, stroke_width=3,
                stroke_fill=(6, 9, 14, 230))

    img.alpha_composite(ov)
    out_dir = os.path.join(REPO, 'tools', 'generated', 'overlays')
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f'{cam_name}.png')
    img.convert('RGB').save(out)
    print(f'-> {out}   ({len(placed)} labels, {len(errs)} marks evalues)')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cam', action='append', default=[])
    ap.add_argument('--no-frame', action='store_true')
    ap.add_argument('--dim', type=float, default=0.35,
                    help='assombrissement de la frame (0=brute, 1=noire)')
    ap.add_argument('--grat-step', type=int, default=5)
    ap.add_argument('--sugg-dist', type=float, default=6000.0)
    ap.add_argument('--no-suggest', action='store_true')
    ap.add_argument('--no-mesh-labels', dest='mesh_labels', action='store_false')
    ap.add_argument('--label-gap', type=int, default=40)
    ap.add_argument('--xval', action='store_true',
                    help='point predit = triangulation SANS cette cam (LOO)')
    args = ap.parse_args()

    px, lms, cams, meshes = load_data()
    targets = args.cam or ['Ambrosia 02 (Panorama)']
    for c in targets:
        if c not in cams:
            print(f'{c}: inconnue, skip')
            continue
        render(c, px, lms, cams, meshes, args)


if __name__ == '__main__':
    main()
