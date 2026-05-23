"""
Migration utility: convert legacy gtamapdata/ to the new solver input format.

Reads:
  gtamapdata/cameras.json — flat dict: name -> {id, player, xyz, ypr, fov, size, source}
  gtamapdata/pixels.json  — nested: cam_name -> lm_name -> [px, py]

Writes:
  observations/pixels.json
  measurements/leak_cams.json          (cams with non-null `player`)
  measurements/bootstrap_hints.json    (initial ypr from legacy cams.ypr, ±5° hint)
  measurements/non_leak_cam_meta.json  (cams without `player`)

Does NOT write:
  observations/horizons.json    (no horizons in legacy)
  measurements/z_constraints.json  (no sea-level markers in legacy)
  measurements/procedural_lms.json (no procedural annotations in legacy)
  measurements/geometry_priors.json (no priors in legacy)

These are the things the user adds manually in the new format. The
migration script keeps a comment file noting candidates the user may
want to annotate.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=False)
        f.write("\n")


def migrate(
    legacy_dir: Path,
    output_dir: Path,
    verbose: bool = True,
) -> Dict[str, int]:
    """Migrate legacy gtamapdata into observations/ and measurements/ subdirs of output_dir.

    Returns:
        Stats dict with counts of each kind of migrated entity.
    """
    cams_legacy = _load_json(legacy_dir / "cameras.json")
    pixels_legacy = _load_json(legacy_dir / "pixels.json")

    leak_cams: Dict[str, Dict[str, Any]] = {}
    non_leak_meta: Dict[str, Dict[str, Any]] = {}
    bootstrap_hints: Dict[str, Dict[str, Any]] = {}

    for cam_name, cam in cams_legacy.items():
        if not isinstance(cam, dict):
            continue
        size = cam.get("size")
        if size is None or len(size) != 2:
            if verbose:
                print(f"  skip cam '{cam_name}' (no size)")
            continue
        ypr = cam.get("ypr", [0, 0, 0])
        fov = cam.get("fov", [60.0, 33.75])
        # fov in legacy is [hfov, vfov]; we use hfov.
        # If hfov is None (legacy stored only vfov), compute hfov from vfov + size.
        if isinstance(fov, list) and len(fov) >= 2:
            hfov_raw = fov[0]
            if hfov_raw is None:
                # Compute hfov from vfov + aspect ratio
                vfov_raw = fov[1]
                if vfov_raw is None:
                    if verbose:
                        print(f"  skip cam '{cam_name}' (both hfov and vfov are None)")
                    continue
                import math
                ratio = size[0] / size[1]
                hfov = math.degrees(2 * math.atan(math.tan(math.radians(float(vfov_raw)) / 2) * ratio))
            else:
                hfov = float(hfov_raw)
        else:
            hfov = float(fov) if fov is not None else 60.0

        # bootstrap hint = current legacy ypr (user can override these
        # manually in the new format if they want true from-scratch)
        bootstrap_hints[cam_name] = {
            "yaw": float(ypr[0]),
            "pitch": float(ypr[1]),
            "roll": float(ypr[2]),
            "confidence": 0.5,
            "reason": "migrated from legacy cameras.json",
        }

        player = cam.get("player")
        if player is not None and len(player) == 3:
            # Leak cam: player gives xyz
            leak_cams[cam_name] = {
                "xyz": [float(player[0]), float(player[1]), float(player[2])],
                "fov": hfov,
                "source": cam.get("source", ""),
                "image_size": [int(size[0]), int(size[1])],
            }
        else:
            # Non-leak cam: just meta
            non_leak_meta[cam_name] = {
                "image_size": [int(size[0]), int(size[1])],
            }

    # Migrate pixel observations
    new_pixels: Dict[str, Dict[str, Dict[str, Any]]] = {}
    n_pixel_obs = 0
    for cam_name, lm_map in pixels_legacy.items():
        if not isinstance(lm_map, dict):
            continue
        new_pixels[cam_name] = {}
        for lm_name, pix in lm_map.items():
            if not isinstance(pix, list) or len(pix) != 2:
                continue
            new_pixels[cam_name][lm_name] = {
                "pixel": [float(pix[0]), float(pix[1])],
            }
            n_pixel_obs += 1

    # Write all outputs
    _save_json(output_dir / "observations" / "pixels.json", new_pixels)
    _save_json(output_dir / "observations" / "horizons.json", {})  # empty stub
    _save_json(output_dir / "measurements" / "leak_cams.json", leak_cams)
    _save_json(output_dir / "measurements" / "non_leak_cam_meta.json", non_leak_meta)
    _save_json(output_dir / "measurements" / "bootstrap_hints.json", bootstrap_hints)
    _save_json(output_dir / "measurements" / "z_constraints.json", {})
    _save_json(output_dir / "measurements" / "procedural_lms.json", {})
    _save_json(output_dir / "measurements" / "geometry_priors.json", {})

    stats = {
        "leak_cams": len(leak_cams),
        "non_leak_cams": len(non_leak_meta),
        "bootstrap_hints": len(bootstrap_hints),
        "pixel_observations": n_pixel_obs,
        "cams_with_pixels": sum(1 for v in new_pixels.values() if v),
    }

    if verbose:
        print()
        print("=== Migration summary ===")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        print()
        print("Files written:")
        for p in [
            "observations/pixels.json",
            "observations/horizons.json",
            "measurements/leak_cams.json",
            "measurements/non_leak_cam_meta.json",
            "measurements/bootstrap_hints.json",
            "measurements/z_constraints.json (empty)",
            "measurements/procedural_lms.json (empty)",
            "measurements/geometry_priors.json (empty)",
        ]:
            print(f"  {output_dir / p}")
        print()
        print("Next steps:")
        print("  1. Edit measurements/z_constraints.json to add sea-level LMs")
        print("  2. Optionally annotate procedural LMs in measurements/procedural_lms.json")
        print("  3. Run: python3 -m solver solve --input . --output .")

    return stats


# ----------------------------------------------------------------------
# Helpers to discover migration candidates from legacy data
# ----------------------------------------------------------------------

def find_procedural_candidates(legacy_dir: Path) -> Dict[str, List[str]]:
    """Scan landmarks.json for naming patterns suggesting procedural LMs.

    Returns a dict {category: list_of_lm_names}. Caller can use this to
    manually populate measurements/procedural_lms.json.
    """
    lms = _load_json(legacy_dir / "landmarks.json")
    candidates: Dict[str, List[str]] = {
        "venetian_paliers": [],
        "portofino_sub_corners": [],
        "other_three_part_naming": [],
    }
    for name in lms:
        if "Venetian Way" in name and re.search(r"\(W\d\)", name):
            candidates["venetian_paliers"].append(name)
        elif "Portofino" in name and re.search(r"\([A-Z]+-[a-zA-Z]+-[A-Z]+\)", name):
            candidates["portofino_sub_corners"].append(name)
        elif re.search(r"\([^)]*-[^)]*-[^)]*\)", name):
            candidates["other_three_part_naming"].append(name)
    return candidates


def find_z_zero_candidates(legacy_dir: Path, keywords: Optional[List[str]] = None) -> List[str]:
    """Scan landmarks.json for LMs whose names suggest they're at z=0.

    Default keywords: sea, water, ocean, beach, marina.
    """
    if keywords is None:
        keywords = ["sea level", "water level", "ocean level"]
    lms = _load_json(legacy_dir / "landmarks.json")
    out = []
    for name in lms:
        nlow = name.lower()
        if any(kw in nlow for kw in keywords):
            out.append(name)
    return out


# ----------------------------------------------------------------------
# CLI entry point
# ----------------------------------------------------------------------

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Migrate legacy gtamapdata to new solver format")
    parser.add_argument(
        "--legacy", type=str, default="gtamapdata",
        help="Path to legacy gtamapdata/ directory (default: gtamapdata)",
    )
    parser.add_argument(
        "--output", type=str, default=".",
        help="Path to output root (will create observations/ and measurements/)",
    )
    parser.add_argument(
        "--discover", action="store_true",
        help="Just print procedural and z=0 candidates, don't migrate",
    )
    args = parser.parse_args()

    legacy_dir = Path(args.legacy)
    output_dir = Path(args.output)

    if not legacy_dir.exists():
        print(f"ERROR: legacy dir {legacy_dir} does not exist", file=sys.stderr)
        return 1

    if args.discover:
        print("=== Procedural candidates ===")
        cand = find_procedural_candidates(legacy_dir)
        for cat, names in cand.items():
            print(f"\n{cat}: {len(names)}")
            for n in names[:5]:
                print(f"  - {n}")
            if len(names) > 5:
                print(f"  ... and {len(names) - 5} more")
        print("\n=== Possible z=0 LMs (by name) ===")
        z_cand = find_z_zero_candidates(legacy_dir)
        print(f"Found {len(z_cand)} candidates")
        for n in z_cand[:10]:
            print(f"  - {n}")
        return 0

    migrate(legacy_dir, output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

