"""
Geometry priors: soft constraints between LMs that the solver tries to
satisfy. Each prior contributes residuals to the bundle adjust pass.

Types:
  - distance: |a - b| = value
  - vertical: a.x = b.x AND a.y = b.y (i.e. a, b on a vertical line)
  - coplanar: 4+ LMs all lie on a common plane (3 LMs define the plane)
  - colinear: 3+ LMs all lie on a common line (2 LMs define the line)
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

import numpy as np


class PriorError(Exception):
    pass


def _residuals_distance(
    lm_xyz: Dict[str, np.ndarray],
    lm_names: List[str],
    value: float,
    weight: float,
) -> List[float]:
    """Residual = weight * (|a - b| - value)."""
    if len(lm_names) != 2:
        raise PriorError(f"distance prior needs 2 LMs, got {len(lm_names)}")
    a = lm_xyz[lm_names[0]]
    b = lm_xyz[lm_names[1]]
    d = float(np.linalg.norm(a - b))
    return [weight * (d - value)]


def _residuals_vertical(
    lm_xyz: Dict[str, np.ndarray],
    lm_names: List[str],
    value: float,  # ignored
    weight: float,
) -> List[float]:
    """Residuals: weight * dx, weight * dy (i.e. a.xy == b.xy)."""
    if len(lm_names) != 2:
        raise PriorError(f"vertical prior needs 2 LMs, got {len(lm_names)}")
    a = lm_xyz[lm_names[0]]
    b = lm_xyz[lm_names[1]]
    return [weight * (a[0] - b[0]), weight * (a[1] - b[1])]


def _residuals_colinear(
    lm_xyz: Dict[str, np.ndarray],
    lm_names: List[str],
    value: float,  # ignored
    weight: float,
) -> List[float]:
    """For each LM beyond the first 2: residual = perpendicular distance
    from the LM to the line through the first 2."""
    if len(lm_names) < 3:
        raise PriorError(f"colinear prior needs 3+ LMs, got {len(lm_names)}")
    a = lm_xyz[lm_names[0]]
    b = lm_xyz[lm_names[1]]
    direction = b - a
    norm = float(np.linalg.norm(direction))
    if norm < 1e-9:
        return [1e3 * weight] * (len(lm_names) - 2)
    direction = direction / norm
    out = []
    for name in lm_names[2:]:
        p = lm_xyz[name]
        # Perp distance = |cross((p-a), direction)|
        offset = p - a
        proj = np.dot(offset, direction) * direction
        perp = offset - proj
        out.append(weight * float(np.linalg.norm(perp)))
    return out


def _residuals_coplanar(
    lm_xyz: Dict[str, np.ndarray],
    lm_names: List[str],
    value: float,  # ignored
    weight: float,
) -> List[float]:
    """For each LM beyond the first 3: residual = perpendicular distance
    from the LM to the plane through the first 3."""
    if len(lm_names) < 4:
        raise PriorError(f"coplanar prior needs 4+ LMs, got {len(lm_names)}")
    a = lm_xyz[lm_names[0]]
    b = lm_xyz[lm_names[1]]
    c = lm_xyz[lm_names[2]]
    normal = np.cross(b - a, c - a)
    norm_len = float(np.linalg.norm(normal))
    if norm_len < 1e-9:
        return [1e3 * weight] * (len(lm_names) - 3)
    normal = normal / norm_len
    out = []
    for name in lm_names[3:]:
        p = lm_xyz[name]
        dist = float(abs(np.dot(p - a, normal)))
        out.append(weight * dist)
    return out


PRIOR_HANDLERS = {
    "distance": _residuals_distance,
    "vertical": _residuals_vertical,
    "colinear": _residuals_colinear,
    "coplanar": _residuals_coplanar,
}


def compute_prior_residuals(
    prior_type: str,
    lm_xyz: Dict[str, np.ndarray],
    lm_names: List[str],
    value: float,
    weight: float,
) -> List[float]:
    """Dispatch to the right handler. Returns list of residual values."""
    if prior_type not in PRIOR_HANDLERS:
        raise PriorError(
            f"Unknown prior type '{prior_type}'. Known: {sorted(PRIOR_HANDLERS.keys())}"
        )
    handler = PRIOR_HANDLERS[prior_type]
    return handler(lm_xyz, lm_names, value if value is not None else 0.0, weight)


def n_residuals_for_prior(prior_type: str, n_lms: int) -> int:
    """Predict how many residuals a prior of this type will produce."""
    if prior_type == "distance":
        return 1
    if prior_type == "vertical":
        return 2
    if prior_type == "colinear":
        return max(0, n_lms - 2)
    if prior_type == "coplanar":
        return max(0, n_lms - 3)
    raise PriorError(f"Unknown prior type '{prior_type}'")

