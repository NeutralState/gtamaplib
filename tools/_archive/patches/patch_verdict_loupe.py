#!/usr/bin/env python3
# VERDICT-V1 + LOUPE-GL-V1 (2026-07-09).
# VERDICT: residuel instantane au clic — quand un pixel est ajoute/deplace sur
# un LM qui a un xyz, le serveur calcule le residuel du rayon et l'UI toast le
# verdict (vert <4' / ambre <12' / rouge au-dela). Le feedback passe d'un
# cycle complet a zero seconde (lecon MSE: marking pourri decouvert une
# session plus tard). Wrapper fetch = zero modification des 6 sites d'appel.
# Teste live au sandbox: le pixel NEXT-CLICK de Tresor Tower verifie a 0.6'.
# LOUPE-GL: quand l'image-adjust est actif, la loupe lit le canvas GL (coords
# 1:1) — tu zoomes sur ce que tu VOIS, pas les pixels bruts. Requiert
# preserveDrawingBuffer (sinon drawImage depuis un canvas GL retourne vide).
# Idempotent.
import sys

p = 'tools/server.py'
src = open(p).read()
if 'VERDICT-V1' in src:
    print(f'ok  {p}: deja patche')
else:
    old = """            ml.get_camera.cache_clear()
            print(f"Added pixel {lm_name} in {cam_name}: ({px_x}, {px_y})")
            self.send_json({'ok': True, 'is_new': is_new})"""
    new = """            ml.get_camera.cache_clear()
            print(f"Added pixel {lm_name} in {cam_name}: ({px_x}, {px_y})")
            # [VERDICT-V1] residuel instantane du rayon vs xyz existant du LM.
            # Non-bloquant: un verdict qui plante ne bloque jamais l'ecriture.
            verdict = None
            try:
                xyz_v = md.landmarks.get(lm_name)
                if xyz_v is not None:
                    sys.path.insert(0, TOOL_DIR)
                    from common import get_cam as _gc, residual_dual as _rd
                    _cam = _gc(cam_name)
                    if _cam is not None:
                        _a, _g, _d = _rd(_cam, (px_x, px_y), list(xyz_v))
                        if _a is not None:
                            verdict = {'arcmin': round(_a, 1),
                                       'meters': None if _g is None else round(_g, 2),
                                       'dist': round(_d) if _d else None}
            except Exception:
                pass
            self.send_json({'ok': True, 'is_new': is_new, 'verdict': verdict})"""
    assert old in src, 'ancre add_pixel introuvable'
    src = src.replace(old, new, 1)
    old = """            ml.get_camera.cache_clear()
            print(f"Set pixel {lm_name} in {cam_name}: ({px_x}, {px_y})")
            self.send_json({'ok': True})"""
    new = """            ml.get_camera.cache_clear()
            print(f"Set pixel {lm_name} in {cam_name}: ({px_x}, {px_y})")
            verdict = None   # [VERDICT-V1] meme feedback au drag/set
            try:
                xyz_v = md.landmarks.get(lm_name)
                if xyz_v is not None:
                    sys.path.insert(0, TOOL_DIR)
                    from common import get_cam as _gc, residual_dual as _rd
                    _cam = _gc(cam_name)
                    if _cam is not None:
                        _a, _g, _d = _rd(_cam, (px_x, px_y), list(xyz_v))
                        if _a is not None:
                            verdict = {'arcmin': round(_a, 1),
                                       'meters': None if _g is None else round(_g, 2),
                                       'dist': round(_d) if _d else None}
            except Exception:
                pass
            self.send_json({'ok': True, 'verdict': verdict})"""
    assert old in src, 'ancre set_pixel introuvable'
    src = src.replace(old, new, 1)
    open(p, 'w').write(src)
    print(f'EDIT {p}: verdict sur add_pixel + set_pixel')

p = 'tools/calib.html'
src = open(p).read()
did = []
if 'VERDICT-V1' not in src:
    TOAST = '''
<!-- [VERDICT-V1] toast de verdict instantane au clic (wrapper fetch, zero
     modification des sites d'appel existants). -->
<div id="vd-toast" style="display:none;position:fixed;bottom:26px;left:50%;transform:translateX(-50%);
     z-index:500;padding:8px 16px;border-radius:8px;font-family:var(--mono,monospace);font-size:12.5px;
     box-shadow:0 6px 24px #000c;pointer-events:none;border:1px solid"></div>
<script>
(function () {
  const toast = document.getElementById('vd-toast');
  let timer = null;
  function show(lm, v) {
    let col, icon, msg;
    if (v.arcmin < 4)       { col = '#4ade80'; icon = '\\u2713'; msg = 'solide'; }
    else if (v.arcmin < 12) { col = '#f59e0b'; icon = '\\u26a0'; msg = 'a verifier'; }
    else                    { col = '#f87171'; icon = '\\u2715'; msg = 'mauvais feature?'; }
    const m = v.meters != null ? ' / ' + v.meters + 'm' : '';
    toast.textContent = icon + ' ' + lm + ' \\u2014 ' + v.arcmin + "'" + m + ' \\u00b7 ' + msg;
    toast.style.color = col;
    toast.style.borderColor = col;
    toast.style.background = '#0f0f14ee';
    toast.style.display = 'block';
    clearTimeout(timer);
    timer = setTimeout(() => { toast.style.display = 'none'; }, 4000);
  }
  const _fetch = window.fetch;
  window.fetch = function (url, opts) {
    const p = _fetch(url, opts);
    try {
      const u = String(url);
      if (u.includes('/api/add_pixel') || u.includes('/api/set_pixel')) {
        p.then(r => r.clone().json()).then(d => {
          if (d && d.verdict) {
            const lm = decodeURIComponent((u.match(/[?&]lm=([^&]*)/) || [,''])[1] || '?');
            show(lm, d.verdict);
          }
        }).catch(() => {});
      }
    } catch (e) {}
    return p;
  };
  console.log('[VERDICT-V1] toast actif');
})();
</script>
'''
    assert '</body>' in src
    src = src.replace('</body>', TOAST + '</body>', 1)
    did.append('toast VERDICT')

if 'LOUPE-GL-V1' not in src:
    old = """    if (im.complete && im.naturalWidth) {
      const src = LOUPE / MAG;
      loupeCtx.imageSmoothingEnabled = false;
      loupeCtx.drawImage(im, px[0] - src / 2, px[1] - src / 2, src, src, 0, 0, LOUPE, LOUPE);
    }"""
    new = """    // [LOUPE-GL-V1] si l'image-adjust est actif, la loupe lit le canvas GL
    // (meme resolution que l'img, coords 1:1) — tu zoomes sur ce que tu VOIS.
    const _adjCv = document.getElementById('mkadj-gl');
    const _useGl = _adjCv && _adjCv.style.display === 'block' && _adjCv.width > 0;
    const _srcEl = _useGl ? _adjCv : im;
    if (_useGl || (im.complete && im.naturalWidth)) {
      const src = LOUPE / MAG;
      loupeCtx.imageSmoothingEnabled = false;
      loupeCtx.drawImage(_srcEl, px[0] - src / 2, px[1] - src / 2, src, src, 0, 0, LOUPE, LOUPE);
    }"""
    assert old in src, 'ancre loupe introuvable'
    src = src.replace(old, new, 1)
    did.append('loupe GL')

if 'preserveDrawingBuffer' not in src:
    o1 = "  const gl2 = glCanvas.getContext('webgl2', { premultipliedAlpha: false });\n  const gl = gl2 || glCanvas.getContext('webgl', { premultipliedAlpha: false });"
    n1 = "  const gl2 = glCanvas.getContext('webgl2', { premultipliedAlpha: false, preserveDrawingBuffer: true });\n  const gl = gl2 || glCanvas.getContext('webgl', { premultipliedAlpha: false, preserveDrawingBuffer: true });"
    o2 = "  const gl = glCanvas.getContext('webgl', { premultipliedAlpha: false });"
    n2 = "  const gl = glCanvas.getContext('webgl', { premultipliedAlpha: false, preserveDrawingBuffer: true });"
    if o1 in src:
        src = src.replace(o1, n1, 1); did.append('preserveDrawingBuffer (webgl2)')
    elif o2 in src:
        src = src.replace(o2, n2, 1); did.append('preserveDrawingBuffer (webgl1)')
    else:
        sys.exit('ancre contexte GL introuvable — colle-moi les lignes getContext de ton calib.html')

open(p, 'w').write(src)
print(f'EDIT {p}: ' + ', '.join(did))
