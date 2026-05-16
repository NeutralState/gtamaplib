#!/usr/bin/env python3
"""Extend _PORTOFINO_LM_MAP with 8 additional LMs (mid, base, centroids)."""
import sys, shutil

PATH = 'tools/bundle_adjust.py'
SENTINEL = '[PORTOFINO-RIGID-V1-EXTENDED]'

OLD = '''# [PORTOFINO-RIGID-V1] Portofino Tower (3-peak star building)
_PORTOFINO_LM_MAP = {
    "Portofino Tower (NW)": (1720.3704, -196.3384, 142.3855),
    "Portofino Tower (NE)": (1753.6794, -181.3662, 143.0098),
    "Portofino Tower (S)":  (1734.8100, -223.8500, 140.3500),
}'''

NEW = '''# [PORTOFINO-RIGID-V1-EXTENDED] Portofino Tower (rectangular tower, 3 peaks + base + mid)
_PORTOFINO_LM_MAP = {
    # Top (z~143, building roof)
    "Portofino Tower (NW)": (1721.0972, -196.0548, 143.8115),
    "Portofino Tower (NE)": (1754.8467, -182.0969, 143.3691),
    "Portofino Tower (S)":  (1734.5771, -223.9029, 140.3028),
    "Portofino Tower (T)":  (1736.8403, -200.6849, 142.4945),
    # Mid (z=70, ~floor 21)
    "Portofino Tower (M-NW)": (1721.0972, -196.0548, 70.0000),
    "Portofino Tower (M-NE)": (1754.8467, -182.0969, 70.0000),
    "Portofino Tower (M-S)":  (1734.5771, -223.9029, 70.0000),
    # Base (z=0, ground)
    "Portofino Tower (B-NW)": (1721.0972, -196.0548, 0.0000),
    "Portofino Tower (B-NE)": (1754.8467, -182.0969, 0.0000),
    "Portofino Tower (B-S)":  (1734.5771, -223.9029, 0.0000),
    "Portofino Tower (B)":    (1736.8403, -200.6849, 0.0000),
}'''


def main():
    apply = '--apply' in sys.argv
    with open(PATH) as f:
        content = f.read()
    if SENTINEL in content:
        print(f'{SENTINEL} already applied. Nothing to do.')
        return
    if OLD not in content:
        print('ERROR: OLD block not found')
        sys.exit(1)
    new_content = content.replace(OLD, NEW)
    if not apply:
        print('DRY-RUN OK. Run with --apply to write.')
        return
    shutil.copy(PATH, PATH + '.bak_portofino_extend')
    with open(PATH, 'w') as f: f.write(new_content)
    print(f'Applied. Backup: {PATH}.bak_portofino_extend')


if __name__ == '__main__':
    main()
