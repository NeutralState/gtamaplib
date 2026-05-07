#!/usr/bin/env python3
"""
patch_undo_stack.py — Adds an undo stack to calib.html for pixel operations
(set/add/delete). Each mutation pushes an inverse-operation onto a stack,
and Cmd+Z (or the Undo button) pops + applies it.

Run from gtamaplib-main/:
    python3 tools/patch_undo_stack.py
"""
import os

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == 'tools' \
    else os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(GTAMAP_DIR, 'tools', 'calib.html')

with open(HTML_PATH) as f:
    content = f.read()

if 'undoStack' in content:
    print("• Undo stack already patched")
    exit(0)

# ── 1. Add CSS for undo button ────────────────────────────────────────────────
NEW_CSS = """
/* Undo button in header */
#btn-undo{font-family:var(--mono);font-size:11px;font-weight:700;padding:5px 10px;border-radius:5px;border:1px solid var(--border);background:var(--surface2);color:var(--mid);cursor:pointer;transition:all .15s}
#btn-undo:hover:not(:disabled){background:var(--surface);border-color:var(--yellow);color:var(--yellow)}
#btn-undo:disabled{opacity:.3;cursor:default}
"""
content = content.replace('</style>', NEW_CSS + '</style>', 1)

# ── 2. Add the Undo button in header — find the .saved span and insert before
SAVED_ANCHOR = '<span id="saved" class="saved">'
UNDO_BTN = '<button id="btn-undo" disabled title="Undo last pixel edit (Cmd+Z)">↶ Undo</button>\n'
content = content.replace(SAVED_ANCHOR, UNDO_BTN + SAVED_ANCHOR, 1)

# ── 3. Inject undo stack logic in JS ──────────────────────────────────────────
# The strategy: define the stack and helper functions globally, wrap each
# mutation API call to push an undo entry first, then provide an undo() that
# pops and applies the inverse op.

UNDO_JS = """
// ── Undo stack for pixel operations ────────────────────────────────────────
// Each entry: { type: 'set'|'add'|'delete', cam, lm, oldPx, newPx, isNew }
//   - 'set':    pixel was at oldPx, moved to newPx → undo by setting back to oldPx
//   - 'add':    pixel was added at newPx (didn't exist before) → undo by deleting
//   - 'delete': pixel was at oldPx, deleted → undo by add_pixel back at oldPx
let undoStack = [];
const UNDO_STACK_LIMIT = 50;
const btnUndo = document.getElementById('btn-undo');

function pushUndo(entry) {
  undoStack.push(entry);
  if (undoStack.length > UNDO_STACK_LIMIT) undoStack.shift();
  updateUndoBtn();
}

function updateUndoBtn() {
  btnUndo.disabled = undoStack.length === 0;
  btnUndo.textContent = undoStack.length > 0 ? `↶ Undo (${undoStack.length})` : '↶ Undo';
}

async function performUndo() {
  if (undoStack.length === 0) return;
  const entry = undoStack.pop();
  updateUndoBtn();
  const camArg = encodeURIComponent(entry.cam);
  const lmArg = encodeURIComponent(entry.lm);
  let url, ok = false;
  try {
    if (entry.type === 'set') {
      // Restore old pixel
      url = `/api/set_pixel?cam=${camArg}&lm=${lmArg}&px=${entry.oldPx[0]}&py=${entry.oldPx[1]}`;
      const r = await fetch(url).then(x => x.json()); ok = r.ok;
    } else if (entry.type === 'add') {
      // Delete the just-added pixel
      url = `/api/delete_pixel?cam=${camArg}&lm=${lmArg}`;
      const r = await fetch(url).then(x => x.json()); ok = r.ok;
    } else if (entry.type === 'delete') {
      // Re-add the pixel at its old position
      url = `/api/add_pixel?cam=${camArg}&lm=${lmArg}&px=${entry.oldPx[0]}&py=${entry.oldPx[1]}`;
      const r = await fetch(url).then(x => x.json()); ok = r.ok;
    }
  } catch (e) {
    console.error('Undo failed:', e);
    alert('Undo failed: ' + e.message);
    return;
  }
  if (!ok) {
    alert('Undo did not succeed (server returned no ok). Stack restored.');
    undoStack.push(entry);
    updateUndoBtn();
    return;
  }
  // Reload to reflect the change visually
  if (currentCam === entry.cam) {
    await loadProjections();
  }
}

btnUndo.addEventListener('click', performUndo);
document.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'z' && !e.shiftKey) {
    // Don't trigger if user is typing in an input
    const tag = document.activeElement?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA') return;
    e.preventDefault();
    performUndo();
  }
});
"""
content = content.replace('</script>', UNDO_JS + '</script>', 1)

# ── 4. Wrap the 3 mutation callsites to push undo entries ─────────────────────

# A. Pixel editor's fix-mode click (set_pixel or add_pixel)
OLD_A = """  const endpoint = pxe.isNew ? '/api/add_pixel' : '/api/set_pixel';
  const newFlag = (pxe.isNew && addPxIsNew) ? '&new=1' : '';
  const res = await fetch(`${endpoint}?cam=${encodeURIComponent(pxe.cam)}&lm=${encodeURIComponent(pxe.lm)}&px=${nx}&py=${ny}${newFlag}`).then(r=>r.json());
  if (res.ok) {
    pxe.curPx = [nx, ny];"""

NEW_A = """  const endpoint = pxe.isNew ? '/api/add_pixel' : '/api/set_pixel';
  const newFlag = (pxe.isNew && addPxIsNew) ? '&new=1' : '';
  const _wasNew = pxe.isNew;
  const _oldPx = pxe.curPx ? [...pxe.curPx] : null;
  const res = await fetch(`${endpoint}?cam=${encodeURIComponent(pxe.cam)}&lm=${encodeURIComponent(pxe.lm)}&px=${nx}&py=${ny}${newFlag}`).then(r=>r.json());
  if (res.ok) {
    pushUndo(_wasNew
      ? { type: 'add', cam: pxe.cam, lm: pxe.lm, newPx: [nx, ny] }
      : { type: 'set', cam: pxe.cam, lm: pxe.lm, oldPx: _oldPx, newPx: [nx, ny] });
    pxe.curPx = [nx, ny];"""

content = content.replace(OLD_A, NEW_A)

# B. Pixel editor's delete button
OLD_B = """  const res = await fetch(`/api/delete_pixel?cam=${encodeURIComponent(pxe.cam)}&lm=${encodeURIComponent(pxe.lm)}`).then(r=>r.json());
  if (res.ok) {
    pxe.validated.add(pxe.cam + '|' + pxe.lm);
    closePxEditor();
    await loadProjections();
  }"""

NEW_B = """  const _delOldPx = pxe.curPx ? [...pxe.curPx] : null;
  const _delCam = pxe.cam;
  const _delLm = pxe.lm;
  const res = await fetch(`/api/delete_pixel?cam=${encodeURIComponent(pxe.cam)}&lm=${encodeURIComponent(pxe.lm)}`).then(r=>r.json());
  if (res.ok) {
    if (_delOldPx) pushUndo({ type: 'delete', cam: _delCam, lm: _delLm, oldPx: _delOldPx });
    pxe.validated.add(_delCam + '|' + _delLm);
    closePxEditor();
    await loadProjections();
  }"""

content = content.replace(OLD_B, NEW_B)

# C. Add-pixel mode (canvas click)
OLD_C = """  // Save pixel
  const res = await fetch(`/api/add_pixel?cam=${encodeURIComponent(currentCam)}&lm=${encodeURIComponent(addPxSelectedLm)}&px=${ix}&py=${iy}`).then(r=>r.json());
  if (res.ok) {
    addPxMode = false;
    document.getElementById('no-img').style.display = 'none';
    canvasWrap.style.cursor = 'crosshair';
    await loadProjections();
  }"""

NEW_C = """  // Save pixel
  const _addCam = currentCam;
  const _addLm = addPxSelectedLm;
  const res = await fetch(`/api/add_pixel?cam=${encodeURIComponent(currentCam)}&lm=${encodeURIComponent(addPxSelectedLm)}&px=${ix}&py=${iy}`).then(r=>r.json());
  if (res.ok) {
    pushUndo({ type: 'add', cam: _addCam, lm: _addLm, newPx: [ix, iy] });
    addPxMode = false;
    document.getElementById('no-img').style.display = 'none';
    canvasWrap.style.cursor = 'crosshair';
    await loadProjections();
  }"""

content = content.replace(OLD_C, NEW_C)

with open(HTML_PATH, 'w') as f:
    f.write(content)

print("✓ Undo stack patched")
print("\nNext steps:")
print("  1. Hard reload calib.html (Cmd+Shift+R)")
print("  2. Edit a pixel, then press Cmd+Z or click '↶ Undo' to revert")
print("  3. Stack is per-session (cleared on reload), max 50 ops")
