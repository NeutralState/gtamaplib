"""
Procedural landmark generators.

A procedural LM is a landmark whose xyz is *computed* from the xyz of
other LMs (its dependencies) via a generator function. Examples:
  - "1000 Venetian Way (W2)" is a palier between (W1) and main roof at
    a known z fraction
  - "Portofino Tower (B-frontL-NW)" is a sub-corner of a face

Generators are pure functions: given resolved LM xyz inputs, return xyz.
They are computed AFTER pixel-anchored LMs have been refined, and they
have NO free degrees of freedom themselves: they're determined by their
deps.

Registry mapping name -> function.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

import numpy as np


# Type: generator(deps_xyz: dict[str, xyz], params: dict) -> xyz
GeneratorFunc = Callable[
    [Dict[str, Tuple[float, float, float]], Dict[str, Any]],
    Tuple[float, float, float],
]


class ProceduralError(Exception):
    """Raised when a generator can't compute (bad params, missing deps)."""


# ----------------------------------------------------------------------
# Built-in generators
# ----------------------------------------------------------------------

def _gen_linear_interpolation(
    deps: Dict[str, Tuple[float, float, float]],
    params: Dict[str, Any],
) -> Tuple[float, float, float]:
    """LM = (1-t) * A + t * B, where A and B are named deps.

    params: {"a": "LM_name_A", "b": "LM_name_B", "t": float in [0,1]}
    """
    a_name = params.get("a")
    b_name = params.get("b")
    t = params.get("t")
    if a_name is None or b_name is None or t is None:
        raise ProceduralError("linear_interpolation requires params {a, b, t}")
    if a_name not in deps or b_name not in deps:
        raise ProceduralError(
            f"linear_interpolation: missing dep '{a_name}' or '{b_name}'"
        )
    a = np.asarray(deps[a_name], dtype=float)
    b = np.asarray(deps[b_name], dtype=float)
    t = float(t)
    p = (1 - t) * a + t * b
    return (float(p[0]), float(p[1]), float(p[2]))


def _gen_weighted_centroid(
    deps: Dict[str, Tuple[float, float, float]],
    params: Dict[str, Any],
) -> Tuple[float, float, float]:
    """LM = (sum_i w_i * dep_i) / sum_i w_i.

    params: {"weights": {"lm_name": w, ...}}.
    If weights omitted, equal weight per dep.
    """
    weights_in = params.get("weights")
    if weights_in is None:
        weights_in = {name: 1.0 for name in deps}
    total_w = 0.0
    accum = np.zeros(3, dtype=float)
    for name, w in weights_in.items():
        if name not in deps:
            raise ProceduralError(f"weighted_centroid: missing dep '{name}'")
        accum += float(w) * np.asarray(deps[name], dtype=float)
        total_w += float(w)
    if total_w == 0:
        raise ProceduralError("weighted_centroid: total weight is zero")
    p = accum / total_w
    return (float(p[0]), float(p[1]), float(p[2]))


def _gen_vertical_offset(
    deps: Dict[str, Tuple[float, float, float]],
    params: Dict[str, Any],
) -> Tuple[float, float, float]:
    """LM = (base.x, base.y, base.z + dz).

    params: {"base": "LM_name", "dz": float}
    """
    base_name = params.get("base")
    dz = params.get("dz")
    if base_name is None or dz is None:
        raise ProceduralError("vertical_offset requires params {base, dz}")
    if base_name not in deps:
        raise ProceduralError(f"vertical_offset: missing dep '{base_name}'")
    base = deps[base_name]
    return (float(base[0]), float(base[1]), float(base[2]) + float(dz))


def _gen_box_corner(
    deps: Dict[str, Tuple[float, float, float]],
    params: Dict[str, Any],
) -> Tuple[float, float, float]:
    """LM = the 4th corner of a parallelogram defined by 3 corners.

    Given corners A, B, C of a parallelogram in order (B is adjacent to
    A and C), the 4th corner D = A + (C - B).

    params: {"a": LM_name, "b": LM_name, "c": LM_name}
    """
    a_name = params.get("a")
    b_name = params.get("b")
    c_name = params.get("c")
    if not all([a_name, b_name, c_name]):
        raise ProceduralError("box_corner requires params {a, b, c}")
    for n in (a_name, b_name, c_name):
        if n not in deps:
            raise ProceduralError(f"box_corner: missing dep '{n}'")
    a = np.asarray(deps[a_name], dtype=float)
    b = np.asarray(deps[b_name], dtype=float)
    c = np.asarray(deps[c_name], dtype=float)
    d = a + (c - b)
    return (float(d[0]), float(d[1]), float(d[2]))


def _gen_face_grid(
    deps: Dict[str, Tuple[float, float, float]],
    params: Dict[str, Any],
) -> Tuple[float, float, float]:
    """LM = bilinear interpolation on a 4-corner face.

    Given corners NW, NE, SW, SE of a quad, and (u, v) in [0,1]x[0,1]:
      top = (1-u)*NW + u*NE
      bot = (1-u)*SW + u*SE
      P   = (1-v)*top + v*bot

    params: {"nw": name, "ne": name, "sw": name, "se": name, "u": float, "v": float}
    """
    needed = ("nw", "ne", "sw", "se", "u", "v")
    for k in needed:
        if k not in params:
            raise ProceduralError(f"face_grid: missing param '{k}'")
    corners = {}
    for key in ("nw", "ne", "sw", "se"):
        n = params[key]
        if n not in deps:
            raise ProceduralError(f"face_grid: missing dep '{n}' (param '{key}')")
        corners[key] = np.asarray(deps[n], dtype=float)
    u = float(params["u"])
    v = float(params["v"])
    top = (1 - u) * corners["nw"] + u * corners["ne"]
    bot = (1 - u) * corners["sw"] + u * corners["se"]
    p = (1 - v) * top + v * bot
    return (float(p[0]), float(p[1]), float(p[2]))


# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------

GENERATORS: Dict[str, GeneratorFunc] = {
    "linear_interpolation": _gen_linear_interpolation,
    "weighted_centroid": _gen_weighted_centroid,
    "vertical_offset": _gen_vertical_offset,
    "box_corner": _gen_box_corner,
    "face_grid": _gen_face_grid,
}


def compute_procedural(
    generator_name: str,
    deps: Dict[str, Tuple[float, float, float]],
    params: Dict[str, Any],
) -> Tuple[float, float, float]:
    """Look up generator and call it. Raises ProceduralError on unknown."""
    if generator_name not in GENERATORS:
        raise ProceduralError(
            f"Unknown generator '{generator_name}'. Known: {sorted(GENERATORS.keys())}"
        )
    return GENERATORS[generator_name](deps, params)


# ----------------------------------------------------------------------
# Topological sort for dependency resolution
# ----------------------------------------------------------------------

def topological_order(
    procedural_specs: Dict[str, Any],
) -> List[str]:
    """Sort procedural LMs so each comes after its dependencies.

    Args:
        procedural_specs: {lm_name: ProceduralLM-like with depends_on}

    Returns:
        List of procedural LM names in dependency order.

    Raises:
        ProceduralError if a cycle is detected.
    """
    names = list(procedural_specs.keys())
    name_set = set(names)
    in_degree = {n: 0 for n in names}
    children: Dict[str, List[str]] = {n: [] for n in names}

    for n, spec in procedural_specs.items():
        for dep in spec.depends_on:
            if dep in name_set:
                in_degree[n] += 1
                children[dep].append(n)

    queue = [n for n, d in in_degree.items() if d == 0]
    out: List[str] = []
    while queue:
        # Pop smallest name first for deterministic order
        queue.sort()
        n = queue.pop(0)
        out.append(n)
        for child in children[n]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(out) < len(names):
        cyclic = [n for n in names if n not in out]
        raise ProceduralError(
            f"Cycle in procedural LM dependencies: {cyclic[:5]}"
        )
    return out

