#!/usr/bin/env python3
# opera_surgery_0709.py -- repose de Vintage VC Outfits 04 (Rooftop) sur
# Opera Tower. One-shot, idempotent-ish.
#
# HYPOTHESE (Alexandre/communaute): la cam est sur le toit d'Opera Tower.
# VALIDATION: la pose actuelle (-566,532,195) satisfaisait 2 appuis sur 4
# (Courthouse 56' et Vizcayne 190' EXCLUS comme "menteurs"); le solve depuis
# le seed Opera reconcilie LES 4 (3-11', RMS ~7'), atterrit a 14m du LM
# Opera Tower (triangule par 5 sources independantes), fov reinterprete
# 42.8->26.2 (autre branche de solution). Les "menteurs" etaient innocents:
# c'est la pose qui etait sur le mauvais building.
# La nouvelle pose est plus VRAIE mais peu CONTRAINTE (4 appuis, sigma ~60m):
# les clics de la session UI (liste fournie) la solidifient.
import json, math, sys
import numpy as np
sys.path.insert(0, 'tools'); sys.path.insert(0, '.')
import common
from common import log_event
from scipy.optimize import least_squares

CAM = 'Vintage Vice City Outfits and Hairstyles 04 (Rooftop)'

cams = json.load(open('gtamapdata/cameras.json'))
meta = cams[CAM]
if math.hypot(meta['xyz'][0] + 424.2, meta['xyz'][1] - 869.4) < 60:
    print('ok  deja sur Opera Tower'); sys.exit(0)

lms = json.load(open('gtamapdata/landmarks.json'))
px = json.load(open('gtamapdata/pixels.json'))[CAM]
obs = [(l, p, lms[l]['xyz']) for l, p in px.items() if (lms.get(l) or {}).get('xyz')]
print(f'{len(obs)} appuis xyz (les 4, exclusions ignorees pour le fit)')

def resid(p):
    st = {'xyz': list(p[:3]), 'ypr': list(p[3:6]), 'fov': [p[6], None]}
    cam = common.get_cam(CAM, cam_state=st)
    return [common.residual_dual(cam, mk, x)[0] or 500.0 for l, mk, x in obs]

p0 = [-424.2, 869.4, 190.0] + list(meta['ypr']) + [meta['fov'][0]]
r = least_squares(resid, p0, method='trf', max_nfev=3000)
rms = math.sqrt(float(np.mean(np.square(r.fun))))
d_op = math.hypot(r.x[0] + 424.2, r.x[1] - 869.4)
print(f"solve Opera: RMS {rms:.2f}' | xyz ({r.x[0]:.1f},{r.x[1]:.1f},{r.x[2]:.1f}) | {d_op:.0f}m du LM Opera Tower")
if rms > 15 or d_op > 60:
    print('SOLVE SUSPECT — rien ecrit'); sys.exit(1)

log_event('opera_surgery', 'repose', cam=CAM, old_xyz=meta['xyz'],
          new_xyz=[round(float(v), 4) for v in r.x[:3]],
          old_fov=meta['fov'][0], new_fov=round(float(r.x[6]), 4),
          reason='pose sur Opera Tower: reconcilie les 2 appuis exclus (Courthouse 56->3, Vizcayne 190->5), 14m du LM Opera Tower (5 sources)')
cams[CAM]['xyz'] = [round(float(v), 6) for v in r.x[:3]]
cams[CAM]['ypr'] = [round(float(v), 6) for v in r.x[3:6]]
cams[CAM]['fov'] = [round(float(r.x[6]), 6), None]
with open('gtamapdata/cameras.json', 'w') as f:
    json.dump(cams, f, indent=2, ensure_ascii=True); f.write('\n')

e = json.load(open('gtamapdata/excluded_markings.json'))
if CAM in e:
    del e[CAM]
    with open('gtamapdata/excluded_markings.json', 'w') as f:
        json.dump(e, f, indent=2, ensure_ascii=True, sort_keys=True); f.write('\n')
    print('2 exclusions retirees (Courthouse, Vizcayne — rehabilitees)')
print('Suite: cycle.')
