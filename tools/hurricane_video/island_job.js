// island_job.js — HURRICANE video v4, the island-wide shot: clear sky, slow orbit over Leonida from the south-east while the sea
// rises 0 -> 8.5 m (Katrina's record surge). Flooded land see-through (uFloodSee), dry land pops (uDryLvl), orbital sea mode
// (water from the arrival map, no map frame / legend). Frames n = 500000 + i to rec_server.py (port 8777).
window.__islandJob = (stride = 1, dur = 17.0) => {
  const FPS = 60, N = Math.round(dur * FPS);
  const ease = x => { x = Math.min(1, Math.max(0, x)); return x * x * (3 - 2 * x); };
  const setS = (id, v) => { const s = document.getElementById(id); s.value = v; s.dispatchEvent(new Event('input')); };
  window.__hurProg = { n: 0, N, done: false, t0: Date.now(), mode: 'island' };
  return (async () => {
    window.__fogOverride = [1e6, 2e6]; setS('env-az', 150); setS('env-el', 35); setS('env-haze', 20);
    window.__groundPlane.visible = false; await window.__orbit(true);
    window.__sunI = 3.4; window.__stormExpo = 1; window.__setGrade(null, 0);
    await window.__hurricane({ surge: 0, storm: 0, sky: 0, rain: 0, lightning: 0 });
    window.__sea.material.uniforms.uFloodSee.value = 1;
    window.__rec = true; let simT = 1000;
    const C0 = [-700, 0], C1 = [-1400, 400], R = 5300;
    for (let i = 0; i < N; i++) {
      const T = i / FPS, k = T / dur;
      const th = (-50 - 30 * ease(k)) * Math.PI / 180;           // swing from the south-east toward the south
      const c = [C0[0] + (C1[0] - C0[0]) * ease(k), C0[1] + (C1[1] - C0[1]) * ease(k)];
      const p = [c[0] + R * Math.cos(th), c[1] + R * Math.sin(th), 1750 + 350 * ease(k)];
      const lv = 8.5 * ease((T - 1.2) / 8.3);
      await window.__hurricane({ surge: lv, storm: 0, sky: 0, rain: 0, lightning: 0 });
      window.__sea.material.uniforms.uFloodSee.value = 1;
      window.__terraUni.uDryLvl.value = lv > 0.05 ? lv : -1e5;
      window.__camSet(p, [c[0], c[1], 0], 50); window.__camFar(120000, 20);
      if (i === 0) { for (let j = 0; j < 20; j++) window.__recFrame(1 / FPS, simT); await new Promise(r => setTimeout(r, 3000)); }
      simT += 1 / FPS; window.__recFrame(1 / FPS, simT);
      if (i % stride === 0) {
        const cv = window.__grabFrame(1920, true); const b = await new Promise(r => cv.toBlob(r, 'image/jpeg', 0.92));
        await fetch(`http://127.0.0.1:8777/frame?n=${500000 + i}&T=${T.toFixed(4)}&level=${lv.toFixed(3)}&mode=island`, { method: 'POST', body: b });
      }
      window.__hurProg.n = i;
    }
    window.__rec = false; window.__hurProg.done = true;
  })();
};
