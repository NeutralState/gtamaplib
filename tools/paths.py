"""paths.py — portable paths (the repo moved 2026-10-09 from ~/Downloads to GTAVI_mapping/Téléchargements). [PATHS-V1]

REPO = the repo root. asset(name) = an external file kept NEXT TO the repo (V16 SVG, leak maps), else in ~/Downloads.
"""
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def asset(name):
    for d in (os.path.dirname(REPO), os.path.expanduser('~/Downloads')):
        p = os.path.join(d, name)
        if os.path.exists(p): return p
    return os.path.join(os.path.dirname(REPO), name)
