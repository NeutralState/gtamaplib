#!/usr/bin/env python3
"""common.py — Shared helpers for the gtamaplib tools.

NE PAS dupliquer ces fonctions dans les outils: la journee du 2026-06-10 a
produit 3 copies de cam_rms, 2 de ray_ls_point et 2 conventions JSON
divergentes (un dump sort_keys/indent=1 a reecrit pixels.json au complet,
8227 insertions de churn pur). Tout nouvel outil importe d'ici.

    sys.path.insert(0, <racine>)
    from tools.common import cam_rms, get_cam, ray_ls_point, save_json
    (ou: sys.path.insert(0, <racine>/tools); from common import ...)
"""
import json
import math
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
import gtamaplib as ml
import gtamapdata as md


# [EXCLUDED-MARKINGS-V1]
_EXCLUDED_MARKINGS = None
def _load_excluded_markings():
    """Charge gtamapdata/excluded_markings.json une fois (cache).
    {cam: [lm,...]} ignores par cam_rms/triangulation, gardes dans pixels.json (UI)."""
    global _EXCLUDED_MARKINGS
    if _EXCLUDED_MARKINGS is None:
        path = os.path.join(_ROOT, "gtamapdata", "excluded_markings.json")
        data = {}
        try:
            with open(path) as f:
                raw = json.load(f)
            for cam, lms in raw.items():
                if not cam.startswith("_") and isinstance(lms, list):
                    data[cam] = set(lms)
        except FileNotFoundError:
            pass
        _EXCLUDED_MARKINGS = data
    return _EXCLUDED_MARKINGS

def is_excluded_marking(cam_name, lm_name):
    """True si (cam_name, lm_name) est exclu du solveur."""
    return lm_name in _load_excluded_markings().get(cam_name, ())

try:
    import numpy as np
except ImportError:  # ray_ls_point devient indisponible, le reste marche
    np = None


def get_cam(cam_name, cam_state=None):
    """Camera prete a projeter. Gotcha #5: chaque ml.get_camera() peut
    retourner une instance differente — on set TOUJOURS xyz/ypr/fov avant
    get_pixel. cam_state optionnel: dict {'xyz','ypr','fov'} (etat simule)
    au lieu de l'etat disque md.cameras."""
    cam = ml.get_camera(cam_name)
    st = cam_state if cam_state is not None else md.cameras[cam_name]
    cam.set_xyz(tuple(st["xyz"]))
    cam.set_ypr(tuple(st["ypr"]))
    cam.set_fov(tuple(st["fov"]))
    return cam


def cam_rms(cam_name, lm_override=None, cam_state=None, lms=None):
    """RMS arcmin d'une cam — LA formule canonique (identique a
    compute_confidence_tiers): dx*hfov/w*60, dy*vfov/h*60, sqrt(mean(d2)).

    lm_override: dict {lm_name: xyz} prioritaire sur l'etat courant.
    lms: dict complet {lm_name: xyz|None} remplacant md.landmarks (etat
         simule, ex: guarded_apply). lm_override s'applique par-dessus.
    Retourne None si aucune observation valide."""
    obs = md.pixels.get(cam_name)
    if not obs or cam_name not in md.cameras:
        return None
    cam = get_cam(cam_name, cam_state)
    base = lms if lms is not None else md.landmarks
    acc = n = 0
    for ln, px in obs.items():
        if px is None:
            continue
        if is_excluded_marking(cam_name, ln):  # [EXCLUDED-MARKINGS-V1]
            continue
        x = (lm_override or {}).get(ln, base.get(ln))
        if x is None:
            continue
        try:
            p = cam.get_pixel(x)
        except Exception:
            continue
        if p is None:
            continue
        dx = (p[0] - px[0]) * cam.hfov / cam.w * 60
        dy = (p[1] - px[1]) * cam.vfov / cam.h * 60
        acc += dx * dx + dy * dy
        n += 1
    return math.sqrt(acc / n) if n else None


# ── DUAL-METRIC-V1 (2026-07-07) ─────────────────────────────────────────
# L'erreur angulaire explose mecaniquement a courte portee (0.9m lateral a
# 15-20m = 188'): 9 des 20 WAR du scan etaient des artefacts metriques.
# Le discriminant honnete = l'ecart transverse rayon<->point en METRES.
# L'arcmin reste la mesure du BA et des LM lointains; le metre juge la
# courte portee. Verdicts sains = dual (voir find_fossils, collision_scan V2).

FOSSIL_GAP_M = 3.0


_COV_CACHE = None

def lm_sigma_m(lm_name):
    """Sigma (m, norme xyz) du LM depuis le dernier covariances.json du BA
    [COVARIANCE-V1]. None si le LM n'etait pas dans le solve ou pas de fichier.
    Usage gates: delta statistiquement insignifiant si delta <= 3*sigma."""
    global _COV_CACHE
    if _COV_CACHE is None:
        try:
            import os as _os
            p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                              'generated', 'covariances.json')
            _COV_CACHE = json.load(open(p)).get('lms', {})
        except Exception:
            _COV_CACHE = {}
    e = _COV_CACHE.get(lm_name)
    return None if e is None else e.get('sigma_m')


# ── PROVENANCE-V2 (2026-07-08): journal append-only ─────────────────────
# Chaque ecriture outillee loggue dans gtamapdata/events.jsonl (commite).
# Historique de provenance ET filet de recuperation (la quarantaine
# d'orphelins loggue l'ancien xyz -> reversible).

def log_event(tool, action, **payload):
    import os as _os, datetime as _dt
    base = _os.path.dirname(_os.path.abspath(__file__))
    p = _os.path.join(base, '..', 'gtamapdata', 'events.jsonl')
    ev = {'ts': _dt.datetime.now().isoformat(timespec='seconds'),
          'tool': tool, 'action': action}
    ev.update(payload)
    try:
        with open(p, 'a') as f:
            f.write(json.dumps(ev, ensure_ascii=True) + '\n')
    except Exception:
        pass


_COV_CACHE_CAMS = None
_LEAK_CLASS_CACHE = None

def cam_sigma_pos(cam_name):
    # Sigma position (m) de la cam [COVARIANCE-V1 / SIGMA-POOL-V1]:
    # - covariances.json si la cam etait dans le dernier solve
    # - 0.0 si xyz HUD-locked (classes A/B/C du leak_cam_audit)
    # - None sinon (inconnue = neutre, jamais penalisee)
    global _COV_CACHE_CAMS, _LEAK_CLASS_CACHE
    import os as _os
    base = _os.path.dirname(_os.path.abspath(__file__))
    if _COV_CACHE_CAMS is None:
        try:
            _COV_CACHE_CAMS = json.load(open(_os.path.join(base, 'generated', 'covariances.json'))).get('cams', {})
        except Exception:
            _COV_CACHE_CAMS = {}
    e = _COV_CACHE_CAMS.get(cam_name)
    if e is not None:
        return e.get('sigma_pos_m')
    if _LEAK_CLASS_CACHE is None:
        try:
            a = json.load(open(_os.path.join(base, '..', 'gtamapdata', 'leak_cam_audit.json')))
            _LEAK_CLASS_CACHE = {n: (v or {}).get('constraint_class') for n, v in a.items()}
        except Exception:
            _LEAK_CLASS_CACHE = {}
    cls = _LEAK_CLASS_CACHE.get(cam_name) or ''
    if cls.startswith(('A_', 'B_', 'C_')):
        return 0.0
    return None


# [SIGMA-TRI-V1] priors angulaires (arcmin) quand la cam n'est pas dans le
# dernier solve BA. Classes A = ypr HUD (quasi-verite), B/C = ypr refine sur
# ancres (bon), inconnu = prudent.
SIGMA_ANG_CLASS_A = 1.0
SIGMA_ANG_CLASS_BC = 3.0
SIGMA_ANG_UNKNOWN = 8.0


def cam_sigma_ang_arcmin(cam_name):
    """Sigma DIRECTION du rayon (arcmin) [SIGMA-TRI-V1]:
    - covariances.json (sigma_ypr yaw/pitch en quadrature) si la cam etait
      dans le dernier solve BA
    - prior par classe sinon (A=1', B/C=3', inconnu=8').
    Le roll est ignore (transverse negligeable pres du centre image)."""
    global _COV_CACHE_CAMS, _LEAK_CLASS_CACHE
    import os as _os
    base = _os.path.dirname(_os.path.abspath(__file__))
    if _COV_CACHE_CAMS is None:
        cam_sigma_pos(cam_name)  # peuple les deux caches
    e = _COV_CACHE_CAMS.get(cam_name)
    if e is not None and e.get('sigma_ypr_deg'):
        sy, sp = e['sigma_ypr_deg'][0], e['sigma_ypr_deg'][1]
        return math.hypot(sy, sp) * 60.0
    if _LEAK_CLASS_CACHE is None:
        cam_sigma_pos(cam_name)
    cls = _LEAK_CLASS_CACHE.get(cam_name) or ''
    if cls.startswith('A_'):
        return SIGMA_ANG_CLASS_A
    if cls.startswith(('B_', 'C_')):
        return SIGMA_ANG_CLASS_BC
    return SIGMA_ANG_UNKNOWN


def ray_sigma_m(cam_name, dist_m, px_noise_arcmin=0.0):
    """Sigma TRANSVERSE (metres) d'un rayon au point situe a dist_m
    [SIGMA-TRI-V1]: sigma_ray^2 = sigma_pos^2 + (sigma_ang * dist)^2.
    sigma_pos None (inconnue) -> prior 5m. px_noise_arcmin s'ajoute en
    quadrature au sigma angulaire (bruit de marquage, ~1.5px converti par
    l'appelant qui connait hfov/w)."""
    sp = cam_sigma_pos(cam_name)
    if sp is None:
        sp = 5.0
    sa = math.hypot(cam_sigma_ang_arcmin(cam_name), px_noise_arcmin)
    return math.sqrt(sp * sp + (math.radians(sa / 60.0) * dist_m) ** 2)


def residual_dual(cam, mk, xyz):
    """(arcmin, gap_m, dist_m) pour une observation (cam deja instanciee).
    gap_m = ecart transverse du rayon(marking) au point; None si direction
    indisponible. Retourne (None, None, None) si le point ne projette pas."""
    p = cam.get_pixel(xyz)
    if p is None:
        return None, None, None
    dx = (p[0] - mk[0]) * cam.hfov / cam.w * 60
    dy = (p[1] - mk[1]) * cam.vfov / cam.h * 60
    ang = math.hypot(dx, dy)
    try:
        import numpy as _np
        o = _np.asarray(cam.xyz, dtype=float)
        d = _np.asarray(cam.get_pixel_direction(mk), dtype=float)
        d = d / _np.linalg.norm(d)
        v = _np.asarray(xyz, dtype=float) - o
        t = float(_np.dot(v, d))
        gap = float(_np.linalg.norm(v - max(t, 0.0) * d))
        dist = float(_np.linalg.norm(v))
    except Exception:
        gap = dist = None
    return ang, gap, dist


def cam_rms_dual(cam_name, cam_state=None, lms=None):
    """Version duale de cam_rms — memes filtres exacts (exclusions, None).
    Retourne {'rms_arcmin', 'median_m', 'max_m', 'n'} ou None."""
    obs = md.pixels.get(cam_name)
    if not obs or cam_name not in md.cameras:
        return None
    cam = get_cam(cam_name, cam_state)
    base = lms if lms is not None else md.landmarks
    acc = 0.0
    gaps = []
    n = 0
    for ln, px in obs.items():
        if px is None or is_excluded_marking(cam_name, ln):
            continue
        x = base.get(ln)
        if x is None:
            continue
        try:
            ang, gap, _dist = residual_dual(cam, px, x)
        except Exception:
            continue
        if ang is None:
            continue
        acc += ang * ang
        if gap is not None:
            gaps.append(gap)
        n += 1
    if not n:
        return None
    gaps.sort()
    return {
        'rms_arcmin': math.sqrt(acc / n),
        'median_m': gaps[len(gaps) // 2] if gaps else None,
        'max_m': gaps[-1] if gaps else None,
        'n': n,
    }


def ray_ls_point(rays):
    """Point least-squares minimisant la distance a tous les rayons
    (origin, direction). Releve numpy.linalg.LinAlgError si degenere."""
    A = np.zeros((3, 3)); b = np.zeros(3)
    for o, d in rays:
        d = np.asarray(d, float); d /= np.linalg.norm(d)
        P = np.eye(3) - np.outer(d, d)
        A += P; b += P @ np.asarray(o, float)
    return np.linalg.solve(A, b)


def pixel_observers(require_existing_cam=True):
    """Index {lm_name: [cam_names]} des markings non-nuls."""
    out = {}
    for c, obs in md.pixels.items():
        if require_existing_cam and c not in md.cameras:
            continue
        for l, px in obs.items():
            if px is not None:
                out.setdefault(l, []).append(c)
    return out


def save_json(path, data):
    """Ecriture canonique du projet: indent=2, SANS sort_keys (ordre
    d'insertion preserve, comme gtamapdata.update_*), atomique
    (tmp + os.replace — un crash mid-write ne corrompt jamais le fichier)."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


# [FOSSIL-SCAN-V1] A "fossil" is a landmark whose OWN source cameras now
# reject it: its xyz was triangulated/derived from an old pose of a source
# cam, the cam got refined since, the LM stayed frozen. Pattern caught 3x by
# hand during 2026-07 (Easy Hill, the Diner Bays, the WDNA mast sub-points).
FOSSIL_THRESHOLD_ARCMIN = 15.0

def find_fossils(threshold=FOSSIL_THRESHOLD_ARCMIN, gap_threshold_m=FOSSIL_GAP_M):
    """Scan all triangulated LMs; return [{lm, source, resid, n_sources}]
    for every LM where a source cam that still marks it disagrees by more
    than threshold arcmin. Blind spot: a fossil whose source no longer has
    a marking is undetectable (no ray to compare)."""
    import math as _math
    out = []
    for lm, xyz in md.landmarks.items():
        if xyz is None:
            continue
        srcs = (md.landmarks_meta.get(lm) or {}).get('source_cameras', []) or []
        worst = None
        n_checked = 0
        for cn in srcs:
            if cn not in md.cameras or not md.cameras[cn].get('xyz'):
                continue
            px = md.pixels.get(cn, {}).get(lm)
            if px is None or is_excluded_marking(cn, lm):
                continue
            cam = get_cam(cn)
            p = cam.get_pixel(xyz)
            if p is None:
                r, g = float('inf'), None
            else:
                r, g, _d = residual_dual(cam, px, xyz)
                if r is None:
                    r, g = float('inf'), None
            n_checked += 1
            # DUAL-METRIC-V1: fossile seulement si l'angulaire ET le metre
            # condamnent (no-proj = condamne d'office). Anti fausses guerres
            # de courte portee.
            qualifies = (r > threshold) and (g is None or g > gap_threshold_m)
            if qualifies and (worst is None or r > worst[0]):
                worst = (r, cn, g)
        if worst is not None:
            out.append({'lm': lm, 'source': worst[1],
                        'resid': None if worst[0] == float('inf') else round(worst[0], 1),
                        'gap_m': None if worst[2] is None else round(worst[2], 1),
                        'n_sources': len(srcs), 'n_checked': n_checked})
    out.sort(key=lambda x: -(x['resid'] if x['resid'] is not None else 1e9))
    return out
