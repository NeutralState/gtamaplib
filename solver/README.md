# solver/

Clean replacement for the legacy calibration system in `gtamapdata/`.

See `SOLVER_DESIGN.md` at the repo root for the architecture.

## Quick start

```
python -m solver --help
python -m solver solve --verbose
```

## Module map

| Module | Phase | Purpose |
|--------|-------|---------|
| `__main__.py` | 1 | CLI entry point |
| `io.py` | 3 | Load/save JSON files with validation |
| `geometry.py` | 2 | Projection, rays, triangulation math |
| `triangulate.py` | 5 | Multi-cam LM triangulation |
| `calibrate.py` | 5 | Cam ypr / xyz / fov optimization |
| `procedural.py` | 6 | Computes procedural LMs from generators |
| `bootstrap.py` | 4 | Initial guess for all unknowns |
| `solve.py` | 5 | Main iteration loop |
| `migrate_legacy.py` | 7 | One-shot migration from gtamapdata/ |
| `generators/` | 6 | Procedural LM generator functions |

## Status

Phase 1: scaffolding (this commit). All modules are placeholders.
