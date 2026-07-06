"""patch_ui_polish2.py — POLISH-V3.1 (feedback pass, 2026-07-03 soir).

1. Marker hover chips REMOVED (pane 1 + pane 2): they duplicated the
   existing cursor tooltip, which is richer (name + indep status + delta).
   The reticle restyle stays; ghost chips stay (no duplication there).
2. Pose panel COMPACTED: rows flush, values 11px, tighter section paddings
   and titles, discreet copy-pose — the LM list starts much earlier.
Requires patch_ui_polish.py. Idempotent. Hard refresh after.
"""
import shutil, sys
P = 'tools/calib.html'
s = open(P).read()
if 'POLISH-V3.1' in s:
    print('deja patche'); sys.exit(0)
assert 'MARKERS-V2' in s, 'prerequis: patch_ui_polish.py d abord'
shutil.copy(P, P + '.bak_polish2')

old = """      _mv2Reticle(ctx, mx, my, r, color, { hi, dash: lm.is_circular });
      if (hi) {
        const lines = [[lm.name + (lm.is_circular ? '  ↻' : '  ★'), '#e8e8ee']];
        if (lm.delta != null) lines.push(["d = " + lm.delta.toFixed(2) + "'", color]);
        _mv2Chip(ctx, mx, my, lines);
      }
    }"""
assert old in s, 'anchor pane1'
s = s.replace(old, """      _mv2Reticle(ctx, mx, my, r, color, { hi, dash: lm.is_circular });
      // [POLISH-V3.1] no chip here: the existing cursor tooltip already
      // shows name + indep + delta (chip was a duplicate)
    }""", 1)

old = """    _mv2Reticle(ctx2, mx, my, r, color, { hi, dash: lm.is_circular });   // [MARKERS-V2]
    if (hi) {
      const lines = [[lm.name + (lm.is_circular ? '  ↻' : '  ★'), '#e8e8ee']];
      if (lm.delta != null) lines.push(["d = " + lm.delta.toFixed(2) + "'", color]);
      _mv2Chip(ctx2, mx, my, lines);
    }"""
assert old in s, 'anchor pane2'
s = s.replace(old, """    _mv2Reticle(ctx2, mx, my, r, color, { hi, dash: lm.is_circular });   // [MARKERS-V2] [POLISH-V3.1] chip removed (duplicate of tooltip)""", 1)

assert '</style>' in s
s = s.replace('</style>', '\n/* [POLISH-V3.1] compact pose panel — reclaim vertical space for the LM list */\n.sl-row{margin-bottom:0;min-height:0}\n.pv3-val{font-size:11px;padding:1px 6px;letter-spacing:.1px}\n.pv3-val .pv3-unit{font-size:8.5px;margin-left:3px}\n#pv3-copy-pose{margin-top:4px;padding:2px 6px;font-size:9px;opacity:.75}\n#pv3-copy-pose:hover{opacity:1}\n.sb-sec{padding:6px 13px}\n.sb-title{margin-bottom:3px;font-size:8.5px}\n.indep-chip{padding:5px 9px;font-size:10px}\n' + '</style>', 1)
open(P, 'w').write(s)
print('POLISH-V3.1 applique. Hard refresh.')
