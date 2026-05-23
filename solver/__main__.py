"""
CLI entry point for the gtamaplib solver.

Usage:
    python -m solver --help
    python -m solver solve [--input-dir .] [--output-dir .] [--verbose]
    python -m solver validate [--input-dir .]
    python -m solver migrate [--legacy-dir gtamapdata] [--force]
"""

import argparse
import sys

from . import __version__


def cmd_solve(args):
    """Run the solver: read observations + measurements, write inferences."""
    print(f"solve: not yet implemented (Phase 5+)")
    print(f"  input-dir: {args.input_dir}")
    print(f"  output-dir: {args.output_dir}")
    print(f"  verbose: {args.verbose}")
    return 1


def cmd_validate(args):
    """Validate the format of observations and measurements files."""
    print(f"validate: not yet implemented (Phase 3)")
    print(f"  input-dir: {args.input_dir}")
    return 1


def cmd_migrate(args):
    """Migrate from legacy gtamapdata/ format to new observations + measurements."""
    print(f"migrate: not yet implemented (Phase 7)")
    print(f"  legacy-dir: {args.legacy_dir}")
    print(f"  force: {args.force}")
    return 1


def build_parser():
    parser = argparse.ArgumentParser(
        prog="solver",
        description="gtamaplib solver — clean calibration pipeline.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}",
    )

    sub = parser.add_subparsers(dest="command", required=False)

    p_solve = sub.add_parser("solve", help="Run the full solver.")
    p_solve.add_argument("--input-dir", default=".", help="Project root.")
    p_solve.add_argument("--output-dir", default=".", help="Where to write inferences/.")
    p_solve.add_argument("--verbose", "-v", action="store_true")
    p_solve.set_defaults(func=cmd_solve)

    p_val = sub.add_parser("validate", help="Validate input file formats.")
    p_val.add_argument("--input-dir", default=".", help="Project root.")
    p_val.set_defaults(func=cmd_validate)

    p_mig = sub.add_parser("migrate", help="Migrate legacy data to new format.")
    p_mig.add_argument("--legacy-dir", default="gtamapdata", help="Legacy data dir.")
    p_mig.add_argument("--force", action="store_true",
                       help="Overwrite existing observations/measurements.")
    p_mig.set_defaults(func=cmd_migrate)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
