import shutil, sys

P = 'tools/calib.html'
MARK = 'ASSIST-V1'
s = open(P).read()
if MARK in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_assist')

# 1. CSS: bouton visible en single-cam + panneau assist
old = "#proj-toggle{display:none}"
new = """/* [ASSIST-V1] bouton toujours visible; libelle change selon le mode */
#proj-toggle{display:inline-block}
body.assist-on #proj-toggle{background:#f59e0b22;color:#f59e0b;border-color:#f59e0b}
#assist-panel{display:none;position:absolute;top:52px;right:12px;width:270px;max-height:60vh;
  overflow-y:auto;background:var(--surface,#16161c);border:1px solid var(--border,#2a2a33);
  border-radius:8px;padding:10px;z-index:40;font-family:var(--mono,monospace);font-size:11.5px}
body.assist-on #assist-panel{display:block}
#assist-panel h4{margin:0 0 8px;font-size:12px;color:#f59e0b}
#assist-panel .ap-row{padding:4px 6px;border-radius:4px;cursor:pointer;display:flex;gap:6px;align-items:baseline}
#assist-panel .ap-row:hover{background:#ffffff12}
#assist-panel .ap-p1{color:#f59e0b}
#assist-panel .ap-p2{color:#22d3ee}
#assist-panel .ap-name{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}
#assist-panel .ap-why{color:var(--mid,#888);font-size:10px;display:block;margin-left:22px}
#assist-panel .ap-note{color:var(--mid,#888);font-size:10px;margin-top:6px;line-height:1.4}"""
assert old in s, 'css anchor introuvable'
s = s.replace(old, new, 1)

# 2. HTML: panneau (juste apres le bouton proj-toggle)
old = '<button class="rays-toggle" id="proj-toggle" title="Show ghost LM projections on the opposite pane">Projections</button>'
new = '''<button class="rays-toggle" id="proj-toggle" title="Assist: LM non marques projetes en fantomes, priorises par gain">Assist</button>
  <!-- [ASSIST-V1] panneau des LM a marquer, trie par priorite -->
  <div id="assist-panel"><h4>&Agrave; marquer</h4><div id="assist-list"></div>
  <div class="ap-note">Clic sur un fant&ocirc;me ou une ligne = armer le marquage, puis cliquez l'emplacement R&Eacute;EL dans le frame. Sur une cam mal calibr&eacute;e, les positions fant&ocirc;mes sont approximatives &mdash; fiez-vous aux noms.</div></div>'''
assert old in s
s = s.replace(old, new, 1)

# 3. Couleurs par priorite dans drawGhostsOnCtx
old = """  const VIOLET = '#c084fc';
  for (const g of ghosts) {
    if (g.type === 'point') {
      const hi = hoveredName === g.name;
      const [mx, my] = mapper(g.pixel[0], g.pixel[1]);
      const r = hi ? 8 : 5;
      ctxLocal.beginPath(); ctxLocal.arc(mx, my, r, 0, Math.PI * 2);
      ctxLocal.fillStyle = VIOLET + '44';  // 27% alpha fill — matches existing markers
      ctxLocal.fill();
      ctxLocal.strokeStyle = VIOLET; ctxLocal.lineWidth = hi ? 2.5 : 1.5; ctxLocal.stroke();"""
new = """  const VIOLET = '#c084fc';
  // [ASSIST-V1] couleur par priorite quand presente (mode assist)
  const gcol = g => g.priority === 1 ? '#f59e0b' : g.priority === 2 ? '#22d3ee' : VIOLET;
  for (const g of ghosts) {
    if (g.type === 'point') {
      const hi = hoveredName === g.name;
      const COL = gcol(g);
      const [mx, my] = mapper(g.pixel[0], g.pixel[1]);
      const r = hi ? 8 : (g.priority === 1 ? 6 : 5);
      ctxLocal.beginPath(); ctxLocal.arc(mx, my, r, 0, Math.PI * 2);
      ctxLocal.fillStyle = COL + '44';
      ctxLocal.fill();
      ctxLocal.strokeStyle = COL; ctxLocal.lineWidth = hi ? 2.5 : 1.5; ctxLocal.stroke();"""
assert old in s
s = s.replace(old, new, 1)

old = """      ctxLocal.strokeStyle = VIOLET;
      ctxLocal.lineWidth = 1.5;
      ctxLocal.setLineDash([6, 4]);"""
new = """      ctxLocal.strokeStyle = gcol(g);
      ctxLocal.lineWidth = 1.5;
      ctxLocal.setLineDash([6, 4]);"""
assert old in s
s = s.replace(old, new, 1)

# 4. refresh(): branche single-cam assist
old = """    if (document.body.classList.contains('dual-cam') && cam1 && cam2 &&
        !document.body.classList.contains('proj-off')) {
      const d1 = await fetchProjections(cam1, cam2);
      ghostMarkers1 = (d1 && d1.projections) || [];
      const d2 = await fetchProjections(cam2, cam1);
      ghostMarkers2 = (d2 && d2.projections) || [];
    } else {
      ghostMarkers1 = [];
      ghostMarkers2 = [];
    }"""
new = """    if (document.body.classList.contains('dual-cam') && cam1 && cam2 &&
        !document.body.classList.contains('proj-off')) {
      const d1 = await fetchProjections(cam1, cam2);
      ghostMarkers1 = (d1 && d1.projections) || [];
      const d2 = await fetchProjections(cam2, cam1);
      ghostMarkers2 = (d2 && d2.projections) || [];
    } else if (document.body.classList.contains('assist-on') && cam1 &&
               !document.body.classList.contains('dual-cam')) {
      // [ASSIST-V1] mode assist single-cam: ghosts priorises, pas de cache
      // (l'etat change apres chaque add_pixel)
      let d1 = null;
      try {
        const r = await fetch('/api/lm_projections?cam=' + encodeURIComponent(cam1) + '&mode=assist');
        d1 = await r.json();
      } catch (e) { d1 = null; }
      ghostMarkers1 = (d1 && d1.projections) || [];
      ghostMarkers2 = [];
      renderAssistPanel(ghostMarkers1);
    } else {
      ghostMarkers1 = [];
      ghostMarkers2 = [];
      renderAssistPanel([]);
    }"""
assert old in s
s = s.replace(old, new, 1)

# 5. Toggle: en single-cam, le bouton contrôle assist-on
old = """  const btnProj = document.getElementById('proj-toggle');
  if (btnProj) {
    btnProj.addEventListener('click', () => {
      const off = document.body.classList.toggle('proj-off');
      btnProj.classList.toggle('active', !off);
      refresh();
    });
    btnProj.classList.add('active');
  }"""
new = """  const btnProj = document.getElementById('proj-toggle');
  if (btnProj) {
    btnProj.addEventListener('click', () => {
      if (document.body.classList.contains('dual-cam')) {
        const off = document.body.classList.toggle('proj-off');
        btnProj.classList.toggle('active', !off);
      } else {
        // [ASSIST-V1]
        const on = document.body.classList.toggle('assist-on');
        btnProj.classList.toggle('active', on);
      }
      refresh();
    });
  }

  // [ASSIST-V1] panneau: liste triee, hover = highlight, clic = armer
  window.renderAssistPanel = function(ghosts) {
    const list = document.getElementById('assist-list');
    if (!list) return;
    const pts = ghosts.filter(g => g.priority === 1 || g.priority === 2).slice(0, 30);
    list.innerHTML = '';
    for (const g of pts) {
      const row = document.createElement('div');
      row.className = 'ap-row ap-p' + g.priority;
      row.innerHTML = '<span>P' + g.priority + '</span><span class="ap-name">' + g.name + '</span>' +
                      '<span class="ap-why">' + (g.reason || '') + '</span>';
      row.addEventListener('mouseenter', () => { hoveredGhost1 = g.name; if (typeof draw === 'function') draw(); });
      row.addEventListener('mouseleave', () => { hoveredGhost1 = null; if (typeof draw === 'function') draw(); });
      row.addEventListener('click', () => armGhostMarking(g.name));
      list.appendChild(row);
    }
  };

  // [ASSIST-V1] armer le marquage d'un LM: prochain clic dans le frame = pixel
  window.armGhostMarking = function(lmName) {
    addPxSelectedLm = lmName;
    addPxMode = true;
    canvasWrap.style.cursor = 'crosshair';
    const t = document.getElementById('tri-toast');
    if (t) {
      document.getElementById('tri-toast-title').textContent = 'Marquage arme: ' + lmName;
      document.getElementById('tri-toast-meta').textContent = 'Cliquez l\\'emplacement reel dans le frame (ESC annule)';
      t.style.display = 'block';
      setTimeout(() => { t.style.display = 'none'; }, 4000);
    }
  };"""
assert old in s
s = s.replace(old, new, 1)

# 6. Clic sur un ghost (single-cam, pas en addPxMode) = armer
old = """  if (foundGhost !== hoveredGhost1) { hoveredGhost1 = foundGhost; draw(); }"""
new = """  if (foundGhost !== hoveredGhost1) { hoveredGhost1 = foundGhost; draw(); }
  window._assistHoverGhost = foundGhost;  // [ASSIST-V1] pour le handler de clic"""
assert old in s
s = s.replace(old, new, 1)

old = """canvasWrap.addEventListener('click', async e => {
  if (!addPxMode) return;"""
new = """// [ASSIST-V1] clic sur un fantome en mode assist = armer le marquage
canvasWrap.addEventListener('click', e => {
  if (addPxMode) return;
  if (!document.body.classList.contains('assist-on')) return;
  if (document.body.classList.contains('dual-cam')) return;
  if (window._assistHoverGhost) armGhostMarking(window._assistHoverGhost);
});

canvasWrap.addEventListener('click', async e => {
  if (!addPxMode) return;"""
assert old in s
s = s.replace(old, new, 1)

# 7. Apres un add_pixel reussi, rafraichir les ghosts assist
old = """  if (res.ok) {
    addPxMode = false;
    document.getElementById('no-img').style.display = 'none';
    canvasWrap.style.cursor = 'crosshair';
    await loadProjections();
  }"""
new = """  if (res.ok) {
    addPxMode = false;
    document.getElementById('no-img').style.display = 'none';
    canvasWrap.style.cursor = 'crosshair';
    await loadProjections();
    if (window._refreshGhosts) window._refreshGhosts();  // [ASSIST-V1]
  }"""
assert old in s
s = s.replace(old, new, 1)

open(P, 'w').write(s)
print('ASSIST-V1 client patche (7 edits)')
