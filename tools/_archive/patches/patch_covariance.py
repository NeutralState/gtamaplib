#!/usr/bin/env python3
"""COVARIANCE-V1 Phase A: hook post-solve dans bundle_adjust_weighted —
Cov ~= s2*(J^T J)^-1, sigmas par pose (xyz/ypr/fov) et par LM ecrits dans
tools/generated/covariances.json. Priors/barrieres inclus (confiance effective
du solve). Echelle absolue a calibrer Phase B; classement relatif solide.
Idempotent."""
import sys
p = 'tools/bundle_adjust_weighted.py'
src = open(p).read()
if 'COVARIANCE-V1' in src:
    print('ok  deja patche'); sys.exit(0)

a = """    p_final = result2.x
    final_rms = report_obs_rms(p_final, 'pass2')
else:
    p_final = p1
    final_rms = mid_rms"""
b = """    p_final = result2.x
    final_rms = report_obs_rms(p_final, 'pass2')
    final_result = result2
else:
    p_final = p1
    final_rms = mid_rms
    final_result = result1


# ── COVARIANCE-V1 (2026-07-07): sigma par parametre via diag((J^T J)^-1) ────
# Cov ~= s2 * (J^T J)^-1 avec s2 = 2*cost/(m-n). Le J inclut les barrieres
# (priors vers l'etat initial) — les sigmas sont donc ceux du SYSTEME tel que
# resolu, priors inclus (honnete: c'est la confiance effective du solve).
# Caveat huber: approximation gaussienne au voisinage de la solution.
try:
    import scipy.sparse as _sp
    J = final_result.jac
    JtJ = (J.T @ J)
    if _sp.issparse(JtJ):
        JtJ = JtJ.toarray()
    m_res, n_par = J.shape
    dof = max(1, m_res - n_par)
    s2 = 2.0 * final_result.cost / dof
    diag_cov = s2 * np.diag(np.linalg.pinv(JtJ, rcond=1e-10))
    diag_cov = np.clip(diag_cov, 0, None)
    sig = np.sqrt(diag_cov)
    cov_out = {'meta': {'n_params': int(n_par), 'n_residuals': int(m_res),
                        's2': float(s2), 'note': 'sigmas du systeme BA (priors/barrieres inclus)'},
               'cams': {}, 'lms': {}}
    for n in opt_cams:
        i = cam_idx[n] * CAM_PARAMS
        cov_out['cams'][n] = {
            'sigma_xyz_m': [round(float(v), 4) for v in sig[i:i+3]],
            'sigma_pos_m': round(float(np.linalg.norm(sig[i:i+3])), 4),
            'sigma_ypr_deg': [round(float(v), 5) for v in sig[i+3:i+6]],
            'sigma_hfov_deg': round(float(sig[i+6]), 5),
        }
    for n in opt_lms:
        i = n_cam_params + lm_idx[n] * LM_PARAMS
        cov_out['lms'][n] = {
            'sigma_xyz_m': [round(float(v), 4) for v in sig[i:i+3]],
            'sigma_m': round(float(np.linalg.norm(sig[i:i+3])), 4),
        }
    _cov_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'generated', 'covariances.json')
    with open(_cov_path, 'w') as _f:
        json.dump(cov_out, _f, indent=1, sort_keys=True)
    print(f"\\n[covariance] sigmas ecrits: {_cov_path} (s2={s2:.3f}, dof={dof})")
except Exception as _e:
    print(f"\\n[covariance] echec (non bloquant): {_e}")"""
assert a in src, 'ancre p_final introuvable — bundle a change'
src = src.replace(a, b, 1)
open(p, 'w').write(src)
print('bundle_adjust_weighted patche: COVARIANCE-V1')
