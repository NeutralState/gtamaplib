#!/usr/bin/env python3
"""
patch_yanis_v12_jpg.py

Updates 3 files to switch from yanis V11 (PNG) to V12 (JPG):

1. gtamapdata/maps.json:
   - filename path: maps/yanis,11.png → maps/yanis,12.png
     (used by Python/gtamaplib for triangulation and projection math —
      the raw 20000x20000 master file)

2. tools/server.py:
   - HTTP endpoint /yanis.png → /yanis.jpg
   - Asset file yanis_v11.png → yanis_v12.jpg
   - Content-Type image/png → image/jpeg
   - Error message updated

3. tools/calib.html:
   - All /yanis.png URL references → /yanis.jpg
   - Loading message label unchanged ("yanis map…")

Idempotent via sentinel [YANIS-V12]; safe to re-run.

Run from gtamaplib-main/:
  python3 patch_yanis_v12_jpg.py             # dry-run
  python3 patch_yanis_v12_jpg.py --apply     # write changes
"""
import sys
import shutil
import re
from pathlib import Path

SENTINEL = "[YANIS-V12]"


def patch_maps_json():
    """Update maps.json to point at yanis,12.png."""
    path = Path("gtamapdata/maps.json")
    text = path.read_text()
    old = "maps/yanis,11.png"
    new = "maps/yanis,12.png"
    if old not in text and new in text:
        return path, text, text, "already at V12"
    if old not in text:
        return path, text, None, "ERROR: no yanis,11.png reference found"
    new_text = text.replace(old, new)
    return path, text, new_text, "yanis,11.png → yanis,12.png"


def patch_server_py():
    """Update server.py to serve yanis_v12.jpg via /yanis.jpg."""
    path = Path("tools/server.py")
    text = path.read_text()

    if SENTINEL in text:
        return path, text, text, f"sentinel {SENTINEL} found, already patched"

    new_text = text

    # Replace endpoint URL
    new_text = new_text.replace("path == '/yanis.png'", f"path == '/yanis.jpg'  # {SENTINEL}")

    # Replace asset filename (line 380 area)
    new_text = new_text.replace("'yanis_v11.png'", "'yanis_v12.jpg'")

    # Replace error message
    new_text = new_text.replace(
        b"yanis_v11.png not found in tools/assets/".decode(),
        b"yanis_v12.jpg not found in tools/assets/".decode(),
    )

    # Replace Content-Type header
    new_text = new_text.replace(
        "self.send_header('Content-Type', 'image/png')",
        "self.send_header('Content-Type', 'image/jpeg')",
        1,  # only the first occurrence (the /yanis.png/jpg one)
    )

    if new_text == text:
        return path, text, None, "ERROR: no changes made (patterns not found)"
    return path, text, new_text, "endpoint+asset+content-type → V12 JPG"


def patch_calib_html():
    """Replace /yanis.png URLs with /yanis.jpg in calib.html."""
    path = Path("tools/calib.html")
    text = path.read_text()

    if SENTINEL in text:
        return path, text, text, f"sentinel {SENTINEL} found, already patched"

    occurrences = text.count("/yanis.png")
    if occurrences == 0:
        return path, text, None, "ERROR: no /yanis.png URLs found"

    new_text = text.replace("/yanis.png", "/yanis.jpg")
    # Add sentinel as a comment at the top of <style> or wherever convenient
    # Just inject as HTML comment near first occurrence
    new_text = new_text.replace(
        "/yanis.jpg",
        "/yanis.jpg",  # keep idempotent — sentinel goes in CSS comment
        1,
    )
    # Inject sentinel near top
    if "<style" in new_text:
        new_text = new_text.replace(
            "<style",
            f"<!-- {SENTINEL} yanis_v12 JPG -->\n<style",
            1,
        )

    return path, text, new_text, f"replaced {occurrences} /yanis.png → /yanis.jpg URLs"


def main():
    apply = "--apply" in sys.argv

    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print()

    patches = [
        ("maps.json", patch_maps_json),
        ("server.py", patch_server_py),
        ("calib.html", patch_calib_html),
    ]

    backups_made = []
    errors = False

    for name, fn in patches:
        path, old_text, new_text, msg = fn()
        if new_text is None:
            print(f"  [ERROR]  {name}: {msg}")
            errors = True
            continue
        if old_text == new_text:
            print(f"  [SKIP]   {name}: {msg}")
            continue
        diff_lines = sum(1 for _ in difflib_unified(old_text, new_text))
        print(f"  [{'PATCH' if apply else 'WOULD'}]  {name}: {msg}")
        if apply:
            backup = path.with_suffix(path.suffix + f".bak_pre_yanis_v12")
            shutil.copy(path, backup)
            backups_made.append(backup)
            path.write_text(new_text)

    print()
    if errors:
        print("ERRORS encountered — review and fix manually.")
        sys.exit(1)

    if apply:
        print(f"✓ patched files; backups in: {[str(b) for b in backups_made]}")
    else:
        print("DRY-RUN — pass --apply to write.")


def difflib_unified(a, b):
    import difflib
    for line in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm=""):
        if line.startswith("+") and not line.startswith("+++"):
            yield line


if __name__ == "__main__":
    main()
