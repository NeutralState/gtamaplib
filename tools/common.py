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
