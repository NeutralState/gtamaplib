#!/usr/bin/env python3
"""seg_occlusion.py — masque « vegetation devant » par segmentation semantique. [SEG-OCC-V1 2026-09-29]

Modele: SegFormer-B2 ADE20K (nvidia/segformer-b2-finetuned-ade-512-512, Hugging Face),
execute dans le venv isole .venv-seg (torch + transformers). La frame est segmentee en
tuiles recouvrantes (les objets lointains sont petits) et le masque vegetation
(tree, plant, grass, palm, flower) est mis en cache en PNG par frame.

Usage (venv): .venv-seg/bin/python tools/seg_occlusion.py "Nom de cam" [--all] [--force]
Lecture (n'importe quel python): load_mask(cam_name) -> bool array HxW ou None
"""
import os, sys
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
CACHE = os.path.join(THIS, 'generated', 'seg_veg')
MODEL = 'nvidia/segformer-b2-finetuned-ade-512-512'
VEG = ('tree', 'plant', 'grass', 'palm', 'flower', 'field')


def _cache_path(cam_name):
    return os.path.join(CACHE, cam_name.replace('/', '_') + '.png')


def load_mask(cam_name):
    import numpy as np
    from PIL import Image
    p = _cache_path(cam_name)
    if not os.path.exists(p): return None
    return np.asarray(Image.open(p).convert('L')) > 127


def segment(cam_name, force=False):
    import numpy as np, torch
    from PIL import Image
    from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation
    out = _cache_path(cam_name)
    if os.path.exists(out) and not force: return out
    global _M, _P
    if '_M' not in globals():
        _P = SegformerImageProcessor.from_pretrained(MODEL)
        _M = SegformerForSemanticSegmentation.from_pretrained(MODEL).eval()
        dev = 'mps' if torch.backends.mps.is_available() else 'cpu'; _M.to(dev); _M._dev = dev
    labels = _M.config.id2label
    veg_ids = [int(i) for i, n in labels.items() if any(v in n.lower() for v in VEG)]
    img0 = Image.open(os.path.join(REPO, 'frames', cam_name + '.png')).convert('RGB'); W0, H0 = img0.size
    sc = min(1.0, 1920.0 / W0); img = img0.resize((int(W0 * sc), int(H0 * sc)), Image.LANCZOS) if sc < 1 else img0
    W, H = img.size
    T = 768; st = 512
    # memoire bornee: meilleure classe + son logit par pixel (pas de tenseur 150 x H x W: 5 Go en 4K)
    best = np.full((H, W), -np.inf, np.float32); cls = np.zeros((H, W), np.uint8)
    xs = list(range(0, max(W - T, 0) + 1, st)) + ([W - T] if W > T and (W - T) % st else [])
    ys = list(range(0, max(H - T, 0) + 1, st)) + ([H - T] if H > T and (H - T) % st else [])
    for y in ys or [0]:
        for x in xs or [0]:
            tile = img.crop((x, y, min(x + T, W), min(y + T, H)))
            inp = _P(images=tile, return_tensors='pt').to(_M._dev)
            with torch.no_grad():
                lg = _M(**inp).logits
                lg = torch.nn.functional.interpolate(lg, size=(tile.height, tile.width), mode='bilinear', align_corners=False)[0]
                mx, am = lg.max(0)
            mx = mx.float().cpu().numpy(); am = am.cpu().numpy().astype(np.uint8)
            sl = (slice(y, y + tile.height), slice(x, x + tile.width)); upd = mx > best[sl]
            best[sl][upd] = mx[upd]; cls[sl][upd] = am[upd]
    del best
    if sc < 1: cls = np.asarray(Image.fromarray(cls).resize((W0, H0), Image.NEAREST))
    veg = np.isin(cls, veg_ids)
    os.makedirs(CACHE, exist_ok=True)
    Image.fromarray((veg * 255).astype(np.uint8)).save(out)
    np.save(out.replace('.png', '_cls.npy'), cls.astype(np.uint8))
    return out


if __name__ == '__main__':
    import json
    names = list(json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))) if '--all' in sys.argv else [a for a in sys.argv[1:] if not a.startswith('--')]
    for n in names:
        if not os.path.exists(os.path.join(REPO, 'frames', n + '.png')): continue
        try: print('ok', segment(n, force='--force' in sys.argv))
        except Exception as e: print('ERREUR', n, e)
