#!/usr/bin/env python3
"""
patch_vendor_hijack_inject.py — Patches all scripts using gtamaplib to
work with the new vendor submodule + sys.modules hijack architecture.

For each affected script:
  1. (audit/ scripts only) Fix the pre-existing path bug:
     `dirname(dirname(__file__))` → `dirname(dirname(dirname(__file__)))`
  2. Inject `import gtamaplib_setup` line right after `sys.path.insert(...)`.

Idempotent via [vendor-hijack-V1] sentinel.

Run from gtamaplib-main/:
    python3 patch_vendor_hijack_inject.py             # dry-run
    python3 patch_vendor_hijack_inject.py --apply     # write changes
"""
import os
import sys
import re

SENTINEL = "[vendor-hijack-V1]"

SKIP_FILES = {"gtamaplib_setup.py", "patch_vendor_hijack_inject.py"}
SKIP_DIRS = {"vendor", "_archive"}

INJECT_LINE = f"import gtamaplib_setup  # noqa: F401  {SENTINEL}"


def find_scripts(repo_dir):
    out = []
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            if fn in SKIP_FILES:
                continue
            path = os.path.join(root, fn)
            try:
                with open(path) as f:
                    src = f.read()
            except (OSError, UnicodeDecodeError):
                continue
            if "import gtamaplib" in src:
                out.append(path)
    return sorted(out)


def determine_fix(path, src):
    notes = []

    if SENTINEL in src:
        return {"status": "already_patched", "notes": ["sentinel found"]}

    rel = os.path.relpath(path).replace(os.sep, "/")
    is_audit = "/tools/audit/" in "/" + rel

    new_src = src

    # Step 1: Fix audit/ path bug
    if is_audit:
        old_path_pattern = (
            "os.path.dirname(os.path.dirname(os.path.abspath(__file__)))"
        )
        new_path_pattern = (
            "os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))"
        )
        if old_path_pattern in new_src:
            new_src = new_src.replace(old_path_pattern, new_path_pattern, 1)
            notes.append("fixed path bug (x2 → x3)")

    # Step 2: Inject hijack import right after `sys.path.insert(0, X)`
    # Simple, tolerant pattern: match the insert line, insert our line right after.
    pattern = re.compile(r"(sys\.path\.insert\(0,\s*\w+\)\n)")
    if not pattern.search(new_src):
        return {"status": "no_pattern", "notes": ["no `sys.path.insert(0, VAR)` line found"]}

    new_src = pattern.sub(
        lambda m: m.group(1) + INJECT_LINE + "\n",
        new_src,
        count=1,
    )
    notes.append("injected gtamaplib_setup")

    return {"status": "patch_ready", "new_src": new_src, "notes": notes}


def main():
    apply = "--apply" in sys.argv
    repo_dir = os.path.dirname(os.path.abspath(__file__))

    print(f"Repo dir: {repo_dir}")
    print(f"Mode:     {'APPLY' if apply else 'DRY-RUN'}")
    print()

    scripts = find_scripts(repo_dir)
    print(f"Found {len(scripts)} scripts importing gtamaplib")
    print()

    stats = {"patched": 0, "already": 0, "skipped": 0, "errors": 0}

    for path in scripts:
        rel = os.path.relpath(path, repo_dir)
        with open(path) as f:
            src = f.read()

        result = determine_fix(path, src)
        status = result["status"]
        notes = "; ".join(result["notes"])

        if status == "already_patched":
            print(f"  [SKIP]    {rel}  ({notes})")
            stats["already"] += 1
        elif status == "no_pattern":
            print(f"  [WARN]    {rel}  ({notes})")
            stats["skipped"] += 1
        elif status == "patch_ready":
            tag = "[WOULD]" if not apply else "[PATCH]"
            print(f"  {tag}   {rel}  ({notes})")
            if apply:
                with open(path, "w") as f:
                    f.write(result["new_src"])
            stats["patched"] += 1
        else:
            print(f"  [ERROR]   {rel}  (unknown status: {status})")
            stats["errors"] += 1

    print()
    print(f"Summary: {stats['patched']} patched, {stats['already']} already, "
          f"{stats['skipped']} skipped, {stats['errors']} errors")

    if not apply:
        print()
        print("DRY-RUN — no files changed. Pass --apply to write.")


if __name__ == "__main__":
    main()
