#!/usr/bin/env python3
"""[PORTOFINO-RIGID-V2] Replace _PORTOFINO_LM_MAP with 31-LM star structure."""
import sys, shutil, re

PATH = 'tools/bundle_adjust.py'
SENTINEL = '[PORTOFINO-RIGID-V2]'

NEW_MAP = '''# [PORTOFINO-RIGID-V2] Portofino Tower (3-branch star at 120deg, 5 levels)
_PORTOFINO_LM_MAP = {
    # Top peaks (z~142, LEAK-sourced)
    "Portofino Tower (NW)": (1721.1006, -196.0531, 143.8091),
    "Portofino Tower (NE)": (1754.8517, -182.0989, 143.3679),
    "Portofino Tower (S)":  (1734.5777, -223.9029, 140.3034),
    # Base (z=0)
    "Portofino Tower (BL-NW)": (1718.4210, -205.1606, 0.0000),
    "Portofino Tower (BR-NW)": (1723.7802, -186.9456, 0.0000),
    "Portofino Tower (BL-NE)": (1748.0336, -175.4928, 0.0000),
    "Portofino Tower (BR-NE)": (1761.6698, -188.7050, 0.0000),
    "Portofino Tower (BL-S)":  (1744.0263, -224.8249, 0.0000),
    "Portofino Tower (BR-S)":  (1725.1291, -222.9809, 0.0000),
    "Portofino Tower (B-C)":   (1736.8433, -200.6850, 0.0000),
    # Podium top (z=30)
    "Portofino Tower (PL-NW)": (1718.4210, -205.1606, 30.0000),
    "Portofino Tower (PR-NW)": (1723.7802, -186.9456, 30.0000),
    "Portofino Tower (PL-NE)": (1748.0336, -175.4928, 30.0000),
    "Portofino Tower (PR-NE)": (1761.6698, -188.7050, 30.0000),
    "Portofino Tower (PL-S)":  (1744.0263, -224.8249, 30.0000),
    "Portofino Tower (PR-S)":  (1725.1291, -222.9809, 30.0000),
    "Portofino Tower (P-C)":   (1736.8433, -200.6850, 30.0000),
    # Mid break (z=90)
    "Portofino Tower (ML-NW)": (1718.4210, -205.1606, 90.0000),
    "Portofino Tower (MR-NW)": (1723.7802, -186.9456, 90.0000),
    "Portofino Tower (ML-NE)": (1748.0336, -175.4928, 90.0000),
    "Portofino Tower (MR-NE)": (1761.6698, -188.7050, 90.0000),
    "Portofino Tower (ML-S)":  (1744.0263, -224.8249, 90.0000),
    "Portofino Tower (MR-S)":  (1725.1291, -222.9809, 90.0000),
    "Portofino Tower (M-C)":   (1736.8433, -200.6850, 90.0000),
    # High / branches start (z=110)
    "Portofino Tower (HL-NW)": (1718.4210, -205.1606, 110.0000),
    "Portofino Tower (HR-NW)": (1723.7802, -186.9456, 110.0000),
    "Portofino Tower (HL-NE)": (1748.0336, -175.4928, 110.0000),
    "Portofino Tower (HR-NE)": (1761.6698, -188.7050, 110.0000),
    "Portofino Tower (HL-S)":  (1744.0263, -224.8249, 110.0000),
    "Portofino Tower (HR-S)":  (1725.1291, -222.9809, 110.0000),
    "Portofino Tower (H-C)":   (1736.8433, -200.6850, 110.0000),
}'''

with open(PATH) as f:
    content = f.read()

if SENTINEL in content:
    print(f'{SENTINEL} already applied')
    sys.exit(0)

# Match the existing _PORTOFINO_LM_MAP block (either V1 or V1-EXTENDED)
pattern = re.compile(
    r'# \[PORTOFINO-RIGID-V1.*?\] Portofino Tower.*?\n_PORTOFINO_LM_MAP = \{.*?\n\}',
    re.DOTALL,
)
m = pattern.search(content)
if not m:
    print('ERROR: existing _PORTOFINO_LM_MAP block not found')
    sys.exit(1)

apply = '--apply' in sys.argv
if not apply:
    print(f'DRY-RUN. Matched block from line ~{content[:m.start()].count(chr(10))+1}')
    print('Run with --apply')
    sys.exit(0)

shutil.copy(PATH, PATH + '.bak_portofino_v2')
new_content = content[:m.start()] + NEW_MAP + content[m.end():]
with open(PATH, 'w') as f: f.write(new_content)
print(f'Applied. Backup: {PATH}.bak_portofino_v2')
