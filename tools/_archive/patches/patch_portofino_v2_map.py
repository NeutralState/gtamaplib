"""[PORTOFINO-RIGID-V3] Update _PORTOFINO_LM_MAP to 115 LMs."""
import sys, shutil, re

PATH = 'tools/bundle_adjust.py'

with open('/tmp/portofino_lm_map.py') as f:
    new_map = f.read()

with open(PATH) as f:
    c = f.read()

pattern = re.compile(r'_PORTOFINO_LM_MAP = \{.*?\n\}\n', re.DOTALL)
m = pattern.search(c)
if not m:
    print('ERROR: _PORTOFINO_LM_MAP not found'); sys.exit(1)

new_c = c[:m.start()] + new_map + '\n' + c[m.end():]

apply = '--apply' in sys.argv
if not apply:
    print(f'DRY-RUN. Replace {m.end()-m.start()} -> {len(new_map)} chars.')
    sys.exit(0)

shutil.copy(PATH, PATH + '.bak_portofino_v2')
with open(PATH, 'w') as f: f.write(new_c)
print('Applied')
