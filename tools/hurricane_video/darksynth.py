"""darksynth.py [out.wav] — an original dark 80s synth track for the Short, synthesized from scratch (no samples, no copyright):
117.5 bpm in D minor (Dm - Bb - C - A), 11 bars on the Short's grid (short_plan.py): 2 bars of intro (drone, filtered arpeggio
opening, riser, heartbeat kick), the drop on bar 3 when the dive bursts out of the clouds (four-on-the-floor kick, gated-reverb
snare, sidechained 16th bass, detuned saw pads, hats), a lead line from bar 7, a final hit on bar 11."""
import sys, os, numpy as np
from scipy.signal import butter, lfilter, fftconvolve
import wave
import short_plan as SP
SR = 48000; BEAT = SP.BEAT; BAR = SP.BAR; NB = 11; D = NB * BAR + 1.5
L = int(D * SR); t = np.arange(L) / SR
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SP.WORK, 'darksynth.wav')
rng = np.random.default_rng(int(os.environ.get('DS_SEED', '80')))
TR = int(os.environ.get('DS_TRANSPOSE', '0'))            # semitones: one variant per Short
def midi(n): return 440.0 * 2 ** ((n + TR - 69) / 12)
def saw(f, n, detune=0.0, ph=0.0):
    tt = np.arange(n) / SR; x = 2 * ((tt * f * (1 + detune) + ph) % 1.0) - 1; return x
def lp(x, fc, order=2):
    b, a = butter(order, min(fc, SR * 0.45) / (SR / 2)); return lfilter(b, a, x)
def hp(x, fc, order=2):
    b, a = butter(order, fc / (SR / 2), 'high'); return lfilter(b, a, x)
def env_adsr(n, a=0.005, d=0.1, s=0.6, r=0.05):
    e = np.ones(n) * s; na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    e[:na] = np.linspace(0, 1, max(na, 1))[:min(na, n)]; e[na:na + nd] = np.linspace(1, s, max(nd, 1))[:max(0, min(nd, n - na))]
    if nr < n: e[-nr:] *= np.linspace(1, 0, nr)
    return e
def place(buf, at, x):
    a = int(at * SR); n = min(len(x), len(buf) - a)
    if n > 0 and a >= 0: buf[a:a + n] += x[:n]
def reverb(x, sec=1.8, mix=0.3, seed=1):
    n = int(sec * SR); ir = np.random.default_rng(seed).standard_normal(n) * np.exp(-np.arange(n) / SR / (sec / 5)); ir = lp(ir, 6000)
    return x * (1 - mix) + fftconvolve(x, ir)[:len(x)] / np.abs(ir).sum() * 9 * mix
DROP = 2 * BAR
CH = [(50, [50, 53, 57]), (46, [46, 50, 53]), (48, [48, 52, 55]), (45, [45, 49, 52])]   # Dm, Bb, C, A (root, triad) midi
def chord_at(tm): return CH[int(tm // BAR) % 4]
# ── kick (four on the floor from the drop; heartbeat in the intro) ──
kick = np.zeros(L)
def kick_hit(amp=1.0):
    n = int(0.45 * SR); tt = np.arange(n) / SR; f = 45 + 110 * np.exp(-tt / 0.035)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.16) * amp + 0.25 * lp(rng.standard_normal(n), 3000) * np.exp(-tt / 0.004) * amp
for b in range(NB * 4):
    tm = b * BEAT
    if tm >= DROP and tm < (NB - 1) * BAR: place(kick, tm, kick_hit(1.0))
    elif tm < DROP and b % 2 == 0: place(kick, tm, kick_hit(0.55 + 0.2 * (b / 8)))
place(kick, (NB - 1) * BAR, kick_hit(1.2))
# sidechain envelope (duck everything but kick on each beat after the drop)
duck = np.ones(L)
for b in range(NB * 4):
    tm = b * BEAT
    if DROP <= tm < (NB - 1) * BAR:
        a = int(tm * SR); n = int(BEAT * SR); e = 1 - 0.65 * np.exp(-np.arange(n) / SR / 0.09); duck[a:a + n] = np.minimum(duck[a:a + n], e[:L - a])
# ── gated-reverb snare on 2 and 4 ──
snare = np.zeros(L)
def snare_hit():
    n = int(0.5 * SR); tt = np.arange(n) / SR
    body = np.sin(2 * np.pi * 185 * tt) * np.exp(-tt / 0.05) * 0.6
    nz = lp(hp(rng.standard_normal(n), 900), 6500) * np.exp(-tt / 0.07)
    x = body + nz; wet = reverb(np.pad(x, (0, int(0.4 * SR))), 1.2, 0.85, 3)[:n]
    gate = np.clip(1 - (tt - 0.22) / 0.03, 0, 1); return (x * 0.6 + wet * 0.9) * gate
for b in range(NB * 4):
    tm = b * BEAT
    if DROP <= tm < (NB - 1) * BAR and b % 4 in (1, 3): place(snare, tm, snare_hit())
# ── hats (8ths, off-beat accent) ──
hats = np.zeros(L)
for k in range(NB * 8):
    tm = k * BEAT / 2
    if DROP <= tm < (NB - 1) * BAR:
        n = int(0.06 * SR); tt = np.arange(n) / SR; place(hats, tm, lp(hp(rng.standard_normal(n), 7000), 12000) * np.exp(-tt / (0.025 if k % 2 else 0.010)) * (0.10 if k % 2 else 0.05))
# ── bass: 16th notes on the chord root (octave jumps), saw through a low-pass that opens in the intro ──
bass = np.zeros(L)
for k in range(NB * 16):
    tm = k * BEAT / 4
    if tm >= (NB - 1) * BAR: break
    root, _ = chord_at(tm); note = root - 12 + (12 if k % 4 == 2 else 0)
    n = int(BEAT / 4 * SR * 0.95); x = saw(midi(note), n) + 0.6 * saw(midi(note), n, 0.004)
    fc = 300 + 1500 * min(1.0, tm / DROP) ** 2 if tm < DROP else 900 + 500 * (k % 4 == 0)
    place(bass, tm, lp(x, fc) * env_adsr(n, 0.003, 0.08, 0.5, 0.02) * (0.25 if tm < DROP else 0.75))
# ── pads: detuned saw triads, dark low-pass, swell into the drop ──
pads = np.zeros(L)
for bar in range(NB - 1):
    root, tri = chord_at(bar * BAR + 0.01); n = int(BAR * SR)
    x = sum(saw(midi(m), n, d, rng.random()) for m in tri for d in (-0.006, 0.0, 0.007)) / 9
    x += 0.5 * saw(midi(root - 12), n) / 3
    fc = 900 if bar < 2 else 1700
    place(pads, bar * BAR, lp(x, fc, 2) * env_adsr(n, 0.25 if bar >= 2 else 0.8, 0.3, 0.85, 0.15) * (0.30 if bar < 2 else 0.65))
pads = reverb(pads, 2.5, 0.35, 5)
# ── intro drone + riser ──
drone = np.sin(2 * np.pi * midi(38) * t) * 0.18 + saw(midi(26), L) * 0.05
drone = lp(drone, 400) * np.clip(1 - (t - DROP) / 0.4, 0, 1) * np.clip(t / 0.5, 0, 1)
riser = lp(hp(rng.standard_normal(L), 600), 4500) * np.clip((t - 0.6) / (DROP - 0.6), 0, 1) ** 3 * (t < DROP) * 0.10
# ── lead (bars 7-10): slow minor line, square-ish, vibrato, dotted-eighth delay ──
lead = np.zeros(L)
mel = [(6, 0, 74, 1.5), (6, 1.5, 72, 0.5), (6, 2, 69, 2), (7, 0, 70, 1.5), (7, 1.5, 69, 0.5), (7, 2, 65, 2),
       (8, 0, 67, 1.5), (8, 1.5, 69, 0.5), (8, 2, 72, 2), (9, 0, 73, 3), (9, 3, 76, 1)]
for bar, beat, note, dur in mel:
    tm = bar * BAR + beat * BEAT; n = int(dur * BEAT * SR); tt = np.arange(n) / SR
    f = midi(note) * (1 + 0.006 * np.sin(2 * np.pi * 5.5 * tt) * np.clip(tt / 0.3, 0, 1))
    ph = np.cumsum(f) / SR; x = np.sign(np.sin(2 * np.pi * ph)) * 0.5 + (2 * (ph % 1) - 1) * 0.5
    place(lead, tm, lp(x, 2600) * env_adsr(n, 0.02, 0.2, 0.7, 0.12) * 0.32)
dl = np.zeros(L); dly = int(0.75 * BEAT * SR)
for i, g in enumerate((0.45, 0.25, 0.12)): dl[dly * (i + 1):] += lead[:L - dly * (i + 1)] * g
lead = reverb(lead + dl, 2.0, 0.3, 7)
# ── final hit on bar 11 ──
hit = np.zeros(L); n = int(1.5 * SR); tt = np.arange(n) / SR
x = sum(saw(midi(m), n, d) for m in (38, 50, 53, 57) for d in (-0.005, 0.006)) / 8
place(hit, (NB - 1) * BAR, reverb(lp(x, 2500) * np.exp(-tt / 0.5), 2.0, 0.4, 9) * 0.8)
mix = kick * 0.9 + (snare * 0.32 + hats + bass + pads + lead * 1.2) * duck + drone + riser + hit
mix = np.tanh(mix * 1.1) / np.tanh(1.1)
mix = mix[:int((NB * BAR) * SR)]
fade = int(0.04 * SR); mix[:fade] *= np.linspace(0, 1, fade)
st = np.stack([mix, np.roll(mix, int(0.0006 * SR))], 1)                      # a touch of width
st = (st / np.abs(st).max() * 0.92 * 32767).astype(np.int16)
with wave.open(OUT, 'wb') as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
print('ok', OUT, '%.2f s' % (len(mix) / SR))
