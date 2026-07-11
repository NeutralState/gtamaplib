#!/usr/bin/env python3
# GLFIX-REDO (2026-07-09): les GLFIX-V1/V2 avaient ete appliques localement
# puis EMPORTES par le revert de NEXT-TASK (git checkout — ils n'etaient pas
# commites). Sans eux: panel adjust NOIR (WebGL1 + mipmap sur texture
# non-power-of-2 = texture incomplete) et flicker au curseur (draw() reecrit
# cssText et efface visibility). Re-application sur l'etat cc1e80d, COMMITEE
# cette fois. Lecon de process: un fix local non commite est un fix qui
# n'existe pas. Idempotent.
import sys
p = 'tools/calib.html'
src = open(p).read()
if 'GLFIX-V1' in src:
    print('ok  deja patche'); sys.exit(0)
edits = []
o = "  const gl = glCanvas.getContext('webgl', { premultipliedAlpha: false, preserveDrawingBuffer: true });"
n = """  // [GLFIX-V1] WebGL2 d'abord: en WebGL1, mipmap sur texture non-power-of-2
  // (3840x2160) = texture incomplete = echantillonnee NOIRE. WebGL2 = NPOT ok.
  const gl2 = glCanvas.getContext('webgl2', { premultipliedAlpha: false, preserveDrawingBuffer: true });
  const gl = gl2 || glCanvas.getContext('webgl', { premultipliedAlpha: false, preserveDrawingBuffer: true });"""
assert o in src, 'ancre 1 (contexte GL)'
src = src.replace(o, n, 1); edits.append('webgl2-first')
o = """    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, frameImg);
    gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);"""
n = """    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, frameImg);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    if (gl2) {                       // [GLFIX-V1] mipmaps seulement en WebGL2
      gl.generateMipmap(gl.TEXTURE_2D);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
    } else {
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    }
    const err = gl.getError();
    if (err) console.error('[ADJUST-GL] texture err', err);"""
assert o in src, 'ancre 2 (texture)'
src = src.replace(o, n, 1); edits.append('mipmap conditionnel')
o = "#frame-img.mkadj-on, img.mkadj-on { filter: url(#mkadj) !important; }"
n = """#frame-img.mkadj-on, img.mkadj-on { filter: url(#mkadj) !important; }
#frame-img.mkadj-hide { visibility: hidden !important; } /* [GLFIX-V2] survit aux reecritures de cssText par draw() */"""
assert o in src, 'ancre 3 (CSS)'
src = src.replace(o, n, 1); edits.append('classe hide')
o = """      if (texCam !== frameImg.src && frameImg.complete) { glDraw(); }
      frameImg.style.visibility = 'hidden';
    }
    requestAnimationFrame(track);"""
n = """      if (texCam !== frameImg.src && frameImg.complete) { glDraw(); }
    }
    requestAnimationFrame(track);"""
assert o in src, 'ancre 4 (track)'
src = src.replace(o, n, 1); edits.append('track sans visibility')
o = """    if (on) { lastCss = ''; texCam = null; glDraw(); }
    else {
      resetAdj();
      glCanvas.style.display = 'none';
      frameImg.style.visibility = 'visible';
    }"""
n = """    if (on) {
      lastCss = ''; texCam = null;
      frameImg.classList.add('mkadj-hide');   // [GLFIX-V2] rewrite-proof
      glDraw();
    } else {
      resetAdj();
      glCanvas.style.display = 'none';
      frameImg.classList.remove('mkadj-hide');
    }"""
assert o in src, 'ancre 5 (toggle)'
src = src.replace(o, n, 1); edits.append('toggle par classe')
open(p, 'w').write(src)
print('EDIT calib.html 5/5:', ', '.join(edits))
