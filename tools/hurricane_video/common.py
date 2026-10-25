"""common.py — shared paths and helpers of the hurricane video scripts (tools/hurricane_video/).
Renders go to ~/gta6_hurricane_work (NOT /tmp: a reboot wipes it; NOT the repo: the Desktop is synced to iCloud)."""
import os, numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__)); TOOLS = os.path.dirname(HERE); REPO = os.path.dirname(TOOLS)
WORK = os.path.expanduser('~/gta6_hurricane_work'); os.makedirs(WORK, exist_ok=True)
TILES = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,17')
W, H, FPS = 1920, 1080, 60
DEEP = np.array([92, 40, 12], np.float32)          # BGR deep ocean
SHAL = np.array([178, 170, 62], np.float32)        # BGR shallow turquoise
def tile_noise(n, g, seed):
    """tileable smooth value noise, g cells over n px"""
    r = np.random.default_rng(seed).random((g, g)).astype(np.float32)
    big = cv2.resize(np.tile(r, (3, 3)), (3 * n, 3 * n), interpolation=cv2.INTER_CUBIC); return big[n:2 * n, n:2 * n]
def ss(e0, e1, x): t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)
def ease(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)
def lerp(a, b, k): return a + (b - a) * k
def elerp(a, b, k): return float(np.exp(lerp(np.log(a), np.log(b), k)))
