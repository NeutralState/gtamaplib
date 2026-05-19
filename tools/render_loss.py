#!/usr/bin/env python3
"""
[RENDER-LOSS-V1] Render a local XY loss landscape for one camera.

Adapted from rlx's gtamaplib-vc/render_loss.py to work with our fork's
API (cameras.json + landmarks.json + pixels.json + tools/server.py utils).

For each cell (x, y) in a grid around the current camera position:
  - Fix x, y to the cell
  - Optimize remaining params (z, yaw, pitch, roll, hfov)
  - Compute loss (RMS pixel error in arcmin)
  - Color-code: cyan(0.1) → green(1) → yellow(10) → red(100) → magenta(1000)

Uses heap-based BFS to prioritize low-loss cells (faster than full grid).

Output: JSON with samples, suitable for server-side caching + frontend overlay.
"""

import json
import math
import heapq
from pathlib import Path
from typing import Any, Optional

import numpy as np
from scipy.optimize import least_squares

import sys
import os
# Allow import from project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

import gtamaplib as ml
import gtamapdata as md


DEFAULT_CELL_SPACING = 8.0   # meters per cell (4-8m typical)
DEFAULT_BUDGET = 200          # max cells to sample
DEFAULT_MAX_NFEV = 100        # max optimizer iterations per cell


def snap(value: float, spacing: float) -> float:
    return round(float(value) / spacing) * spacing


def pixel_error_at(cam, lm_xyz, mp):
    """Compute pixel error in arcmin (copied from server.py to avoid coupling)."""
    try:
        proj = cam.get_pixel(lm_xyz)
        if proj is None:
            return 1000.0
        dx = float(proj[0]) - mp[0]
        dy = float(proj[1]) - mp[1]
        return math.sqrt((dx * cam.hfov / cam.w) ** 2 + (dy * cam.vfov / cam.h) ** 2) * 60
    except Exception:
        return 1000.0


def build_constraints(cam_name: str) -> list[tuple[str, list[float], list[float], float, bool]]:
    """Build the constraints list (lm_name, lm_xyz, marker_pixel, weight, is_self_source).
    
    Mirrors the logic from server.optimize_camera but without the optimizer.
    Used for both initial state and per-cell loss evaluation.
    """
    TIER_WEIGHTS = {
        'anchor':     1.0,
        'high':       0.8,
        'medium':     0.4,
        'low':        0.1,
        'unverified': 0.0,
    }
    
    _tiers_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'generated', 'confidence_tiers.json')
    try:
        with open(_tiers_path) as f:
            _tier_data = json.load(f)
        _lm_tiers = {n: (d.get('tier') if isinstance(d, dict) else d)
                     for n, d in _tier_data.get('landmarks', {}).items()}
    except Exception:
        _lm_tiers = {}
    
    cam_pixels = md.pixels.get(cam_name, {})
    constraints = []
    for lm, mp in cam_pixels.items():
        lm_xyz = md.landmarks.get(lm)
        if lm_xyz is None:
            continue
        is_self_source = cam_name in md.landmarks_meta.get(lm, {}).get('source_cameras', [])
        tier = _lm_tiers.get(lm, 'unverified')
        base_weight = TIER_WEIGHTS.get(tier, 0.0)
        if base_weight == 0.0:
            continue
        weight = base_weight * (0.3 if is_self_source else 1.0)
        constraints.append((lm, list(lm_xyz), list(mp), weight, is_self_source))
    return constraints


def loss_at_xy(
    cam_name: str,
    x: float,
    y: float,
    start_params: list[float],
    constraints: list,
    max_nfev: int = DEFAULT_MAX_NFEV,
) -> dict[str, Any]:
    """
    Fix x, y; optimize (z, yaw, pitch, roll, hfov) at this position.
    Return the best achievable loss.
    
    start_params: [x, y, z, yaw, pitch, roll, hfov] — starting guess for the rest.
    """
    # Variables to optimize: z, yaw, pitch, roll, hfov (5 params)
    x0 = np.array([start_params[2], start_params[3], start_params[4],
                   start_params[5], start_params[6]], dtype=float)
    
    def residuals(p):
        try:
            cam = ml.get_camera(cam_name)
            cam.set_xyz([x, y, p[0]])
            cam.set_ypr([p[1], p[2], p[3]])
            cam.set_fov((p[4], None))
        except Exception:
            return np.full(2 * len(constraints), 1000.0)
        
        out = []
        for _, lm_xyz, mp, w, _ in constraints:
            try:
                proj = cam.get_pixel(lm_xyz)
                if proj is None:
                    out.extend([1000.0, 1000.0])
                    continue
                dx = (float(proj[0]) - mp[0]) * cam.hfov / cam.w * 60 * w
                dy = (float(proj[1]) - mp[1]) * cam.vfov / cam.h * 60 * w
                out.extend([dx, dy])
            except Exception:
                out.extend([1000.0, 1000.0])
        return np.array(out)
    
    # Bounds: z reasonable, hfov > 0
    lower = np.array([-100.0, -np.inf, -np.inf, -np.inf, 1.0])
    upper = np.array([1000.0, np.inf, np.inf, np.inf, 160.0])
    x0_clipped = np.clip(x0, lower, upper)
    
    try:
        result = least_squares(
            residuals, x0_clipped,
            bounds=(lower, upper),
            loss='huber', f_scale=2.0,
            x_scale='jac',
            max_nfev=max_nfev,
            verbose=0,
        )
        # Compute RMS loss in arcmin (unweighted, for human-readable color)
        final_residuals = residuals(result.x)
        # Divide out weights to get unweighted error
        n = len(constraints)
        errs = []
        for i, (_, _, _, w, _) in enumerate(constraints):
            if w > 0:
                dx = final_residuals[2*i] / w
                dy = final_residuals[2*i+1] / w
                errs.append(math.sqrt(dx*dx + dy*dy))
        rms = math.sqrt(sum(e*e for e in errs) / max(1, len(errs)))
        
        params_full = [x, y, float(result.x[0]), float(result.x[1]),
                       float(result.x[2]), float(result.x[3]), float(result.x[4])]
        return {
            'x': float(x),
            'y': float(y),
            'loss': float(rms),
            'nfev': int(result.nfev),
            'params': params_full,
        }
    except Exception as e:
        return {
            'x': float(x),
            'y': float(y),
            'loss': 9999.0,
            'nfev': 0,
            'params': start_params,
            'error': str(e),
        }


def explore_loss(
    cam_name: str,
    spacing: float = DEFAULT_CELL_SPACING,
    budget: int = DEFAULT_BUDGET,
    max_nfev: int = DEFAULT_MAX_NFEV,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    """
    Heap-based BFS exploration of (x, y) loss landscape around current cam position.
    Returns samples sorted by ascending loss.
    """
    if cam_name not in md.cameras:
        raise KeyError(f'Camera {cam_name!r} not found')
    
    cam_data = md.cameras[cam_name]
    cam_xyz = cam_data.get('xyz') or [0, 0, 0]
    cam_ypr = cam_data.get('ypr') or [0, 0, 0]
    cam_fov = cam_data.get('fov') or [60, None]
    
    initial_params = [
        float(cam_xyz[0]), float(cam_xyz[1]), float(cam_xyz[2]),
        float(cam_ypr[0]), float(cam_ypr[1]), float(cam_ypr[2] if len(cam_ypr) > 2 else 0),
        float(cam_fov[0]),
    ]
    
    constraints = build_constraints(cam_name)
    if len(constraints) < 3:
        raise ValueError(f'Not enough constraints for {cam_name!r} ({len(constraints)} < 3)')
    
    center_x = snap(initial_params[0], spacing)
    center_y = snap(initial_params[1], spacing)
    
    samples: dict[tuple[int, int], dict] = {}
    expanded: set[tuple[int, int]] = set()
    heap: list[tuple[float, int, tuple[int, int]]] = []
    counter = [0]
    
    def evaluate(cell: tuple[int, int], start_params: list[float]) -> None:
        if cell in samples or len(samples) >= budget:
            return
        x = center_x + cell[0] * spacing
        y = center_y + cell[1] * spacing
        sample = loss_at_xy(cam_name, x, y, start_params, constraints, max_nfev)
        sample['grid'] = [int(cell[0]), int(cell[1])]
        samples[cell] = sample
        heapq.heappush(heap, (sample['loss'], counter[0], cell))
        counter[0] += 1
        if verbose and (len(samples) == 1 or len(samples) % 25 == 0):
            print(f"  {len(samples):>4}/{budget} | loss {sample['loss']:.4f}' | x {x:.1f} y {y:.1f}")
    
    evaluate((0, 0), initial_params)
    while heap and len(samples) < budget:
        _loss, _counter, cell = heapq.heappop(heap)
        if cell in expanded:
            continue
        expanded.add(cell)
        parent = samples[cell]['params']
        i, j = cell
        for neighbor in ((i+1, j), (i-1, j), (i, j+1), (i, j-1)):
            evaluate(neighbor, parent)
    
    return sorted(samples.values(), key=lambda r: r['loss'])


def loss_color(loss: float) -> tuple[int, int, int]:
    """Log-scale color: cyan(0.1) → green(1) → yellow(10) → red(100) → magenta(1000) → blue(10000)."""
    colors = [
        (80, 220, 255),   # 0.1 cyan
        (60, 210, 90),    # 1   green
        (255, 220, 40),   # 10  yellow
        (230, 45, 35),    # 100 red
        (225, 55, 230),   # 1000 magenta
        (70, 95, 255),    # 10000 blue
    ]
    value = math.log10(max(float(loss), 1e-12))
    left_power = math.floor(value)
    t = value - left_power
    left_color = colors[(left_power + 1) % len(colors)]
    right_color = colors[(left_power + 2) % len(colors)]
    return tuple(
        int(round(left_color[i] * (1.0 - t) + right_color[i] * t))
        for i in range(3)
    )


def render_loss_data(
    cam_name: str,
    spacing: float = DEFAULT_CELL_SPACING,
    budget: int = DEFAULT_BUDGET,
    max_nfev: int = DEFAULT_MAX_NFEV,
    verbose: bool = False,
) -> dict[str, Any]:
    """Render loss landscape and return JSON-ready dict for caching/UI."""
    samples = explore_loss(cam_name, spacing, budget, max_nfev, verbose)
    
    # Add color info to each sample
    for s in samples:
        r, g, b = loss_color(s['loss'])
        s['color'] = [r, g, b]
    
    # Find min/max for normalization on UI side
    losses = [s['loss'] for s in samples]
    
    return {
        'cam_name': cam_name,
        'spacing': spacing,
        'budget': budget,
        'n_samples': len(samples),
        'loss_min': min(losses) if losses else 0,
        'loss_max': max(losses) if losses else 0,
        'samples': samples,
    }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Render loss landscape for a camera.')
    parser.add_argument('cam_name', help='Camera name')
    parser.add_argument('--spacing', type=float, default=DEFAULT_CELL_SPACING, help='Cell spacing in meters')
    parser.add_argument('--budget', type=int, default=DEFAULT_BUDGET, help='Max number of cells')
    parser.add_argument('--max-nfev', type=int, default=DEFAULT_MAX_NFEV, help='Max optimizer iterations per cell')
    parser.add_argument('--output', type=str, default=None, help='Output JSON path (default: tools/generated/loss_renders/<cam>.json)')
    args = parser.parse_args()
    
    print(f'Rendering loss for {args.cam_name!r} (spacing={args.spacing}m, budget={args.budget}, max_nfev={args.max_nfev})...')
    data = render_loss_data(args.cam_name, args.spacing, args.budget, args.max_nfev, verbose=True)
    
    out_path = args.output
    if out_path is None:
        safe_name = args.cam_name.replace('/', '_').replace(' ', '_').replace('(', '').replace(')', '')
        out_dir = Path(os.path.dirname(os.path.abspath(__file__))) / 'generated' / 'loss_renders'
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f'{safe_name}.json'
    
    with open(out_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f'\nDone. {data["n_samples"]} samples, loss range [{data["loss_min"]:.4f}, {data["loss_max"]:.4f}] arcmin')
    print(f'Saved to: {out_path}')
