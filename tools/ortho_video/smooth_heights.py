"""smooth_heights.py <heights.json> <out.json> [lam] [radius] : lisse les hauteurs le long du reseau: maximise sum_i score_i(h_i) - lam * sum_(i~j) (h_i-h_j)^2
par descente iterative (ICM) sur les voisins (centres a < radius m). Conserve la confiance = pic local du score lisse."""
import sys, json, numpy as np
R = json.load(open(sys.argv[1])); out = sys.argv[2]; lam = float(sys.argv[3]) if len(sys.argv) > 3 else 0.6; rad = float(sys.argv[4]) if len(sys.argv) > 4 else 60.0
keys = list(R); C = np.array([[R[k]['cx'], R[k]['cy']] for k in keys]); hs = np.array(R[keys[0]]['hs']); S = np.array([R[k]['scores'] for k in keys])
S = (S - S.mean(axis=1, keepdims=True)) / (S.std(axis=1, keepdims=True) + 1e-6)
D = np.linalg.norm(C[:, None, :] - C[None, :, :], axis=2); nb = [np.nonzero((D[i] < rad) & (D[i] > 0))[0] for i in range(len(keys))]
h = hs[np.argmax(S, axis=1)].copy()
for it in range(30):
    changed = 0
    for i in np.random.default_rng(it).permutation(len(keys)):
        if len(nb[i]) == 0: continue
        pen = lam * ((hs[None, :] - h[nb[i]][:, None]) ** 2).sum(axis=0) / len(nb[i]) * 4   # penalite moyenne sur les voisins (echelle ~ score z)
        j = int(np.argmax(S[i] - pen)); 
        if hs[j] != h[i]: h[i] = hs[j]; changed += 1
    if changed == 0: break
print('lissage: %d iterations, lam %.2f, voisins median %d' % (it + 1, lam, int(np.median([len(n) for n in nb]))))
for i, k in enumerate(keys):
    R[k]['h_raw'] = R[k]['h']; R[k]['h'] = float(h[i]); R[k]['conf'] = float(max(R[k]['conf'], 2.5)) if len(nb[i]) >= 2 else R[k]['conf']
    R[k].pop('scores', None); R[k].pop('hs', None)
json.dump(R, open(out, 'w')); print('h lisse: mediane %.1f, p25 %.1f, p75 %.1f -> %s' % (np.median(h), np.percentile(h, 25), np.percentile(h, 75), out))
