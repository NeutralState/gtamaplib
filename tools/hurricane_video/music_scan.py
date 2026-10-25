"""music_scan.py <track.mp3> — tempo (autocorrelation of spectral-flux onsets), beat grid and loudness per second, to place a Short's
cuts on the beat and its start just before a drop."""
import sys, subprocess, numpy as np
SR = 22050
x = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', sys.argv[1], '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout, np.float32)
hop = 512; nf = (len(x) - 2048) // hop; win = np.hanning(2048).astype(np.float32)
S = np.abs(np.fft.rfft(np.stack([x[i * hop:i * hop + 2048] * win for i in range(nf)]), axis=1))
flux = np.maximum(np.diff(np.log1p(S), axis=0), 0).sum(1); flux = (flux - flux.mean()) / (flux.std() + 1e-9)
fps = SR / hop; ac = np.correlate(flux, flux, 'full')[len(flux) - 1:]
lags = np.arange(len(ac)); bpm_l = 60 * fps / np.maximum(lags, 1); m = (bpm_l > 80) & (bpm_l < 170)
lag = lags[m][np.argmax(ac[m])]; bpm = 60 * fps / lag
ph = np.argmax([flux[p::lag].sum() for p in range(lag)]); beat0 = ph / fps
rms = np.sqrt(np.convolve(x ** 2, np.ones(SR) / SR, 'same'))[::SR]
print('bpm %.1f  beat0 %.3f s  duration %.1f s' % (bpm, beat0, len(x) / SR))
print('loudness/s:', ' '.join('%d:%.2f' % (i, v) for i, v in enumerate(rms)))
