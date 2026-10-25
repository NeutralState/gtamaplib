// rec_job.js — HURRICANE video, view3d part: loaded in view3d.html (fetch + eval), records frames to rec_server.py (port 8777).
// __hurJob2(mode 'storm'|'calm', stride, nOff, T0, T1): the v2 timeline of view3d shots (only shot 3, Brickell street level
// +5 -> +20 m, is used by the v3 video: T 43-51 s). Frame number = round(T * 60) + nOff (storm 300000, calm 400000).
window.__hurJob2 = (mode, stride, nOff = 0, T0 = 11, T1 = 53) => {
  const FPS = 60;
  const ease = x => { x = Math.min(1, Math.max(0, x)); return x * x * (3 - 2 * x); };
  const lerp = (a, b, k) => a.map((v, i) => v + (b[i] - v) * k);
  const SH = [
    { t0: 11, t1: 21, p0: [700, 200, 120], p1: [960, 330, 150], q0: [1700, 520, 0], q1: [1700, 560, 0], s0: 0.3, s1: 2.0, strikes: [12.2, 17.9] },
    { t0: 21, t1: 30, p0: [-3350, -6950, 400], p1: [-3120, -6680, 330], q0: [-2500, -5900, 0], q1: [-2450, -5850, 0], s0: 2.0, s1: 3.0, strikes: [25.0, 28.6] },
    { t0: 30, t1: 39, p0: [-260, -1340, 175], p1: [-360, -1230, 160], q0: [-760, -880, 10], q1: [-790, -850, 10], s0: 3.0, s1: 5.0, strikes: [32.4, 37.6] },
    { t0: 39, t1: 53, p0: [-120, -1200, 115], p1: [-260, -1010, 100], q0: [-700, -500, 40], q1: [-720, -450, 45], s0: 5.0, s1: 20.0, strikes: [41.0, 44.8, 48.3, 51.5] },
  ];
  const N = Math.round((T1 - T0) * FPS);
  const setS = (id, v) => { const s = document.getElementById(id); s.value = v; s.dispatchEvent(new Event('input')); };
  setS('env-az', 150); setS('env-el', 30); setS('env-haze', 35);
  window.__stormHaze = 9;
  window.__hurProg = { n: 0, N, done: false, t0: Date.now(), mode };
  const storm = mode === 'storm';
  return (async () => {
    window.__rec = true; let prevShot = -1, simT = 1000;
    window.__sunI = storm ? 0.5 : 3.4; window.__stormExpo = storm ? 1.03 : 1; window.__setGrade([0.50, 0.55, 0.58], storm ? 0.2 : 0);
    for (let i = 0; i < N; i++) {
      const T = T0 + i / FPS, n = Math.round(T * FPS), si = SH.findIndex(s => T >= s.t0 && T < s.t1), S = SH[si];
      const k = (T - S.t0) / (S.t1 - S.t0), ke = ease(k);
      const surge = !storm ? 0 : (si === 3 ? S.s0 + (S.s1 - S.s0) * ease((T - 40.5) / 10.5) : S.s0 + (S.s1 - S.s0) * ease(k * 1.08));
      await window.__hurricane(storm ? { surge, storm: 1, sky: 1, rain: 1, wind: 60, lightning: 1e-4 } : { surge: 0, storm: 0, sky: 0, rain: 0, lightning: 0 });
      if (si !== prevShot) { window.__camSet(S.p0, S.q0, 50); prevShot = si; for (let j = 0; j < 20; j++) window.__recFrame(1 / FPS, simT); await new Promise(r => setTimeout(r, 1200)); }
      window.__camSet(lerp(S.p0, S.p1, ke), lerp(S.q0, S.q1, ke), 50);
      if (storm) for (const st of S.strikes) { if (T <= st && T + 1 / FPS > st) window.__strike(); }
      simT += 1 / FPS; window.__recFrame(1 / FPS, simT);
      if (i % stride === 0) {
        const c = window.__grabFrame(1920, true); const b = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.92));
        await fetch(`http://127.0.0.1:8777/frame?n=${n + nOff}&T=${T.toFixed(4)}&shot=${si}&surge=${surge.toFixed(3)}&mode=${mode}`, { method: 'POST', body: b });
      }
      window.__hurProg.n = i;
    }
    window.__rec = false; window.__hurProg.done = true;
  })();
};
