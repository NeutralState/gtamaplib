#!/usr/bin/env python3
"""patch_sigma_gates.py -- SIGMA-GATES-V1 + OBSERVER-GUARD-V1 (Phase B tranche 1).

1. tools/common.py: lm_sigma_m() — sigma du LM depuis covariances.json (cache).
2. harvest_run.py: gate delta relative au sigma (delta <= max(15m, 3*sigma))
   + gate ALL-OBSERVER (regle Flagler EN CODE: le point propose doit satisfaire
   TOUS les observers non-exclus <8', pas juste le pool retenu).
3. tools/audit/collision_scan.py: meme gate delta relative.
4. tools/triangulate_lm.py: print "All-observer residual" au point final
   (le pool peut ecarter silencieusement un observer sain — Flagler: pool 2.2'
   mais Interchange 0.0->23.4').

Validation sandbox: Flagler -> REVIEW (all-obs 23.4), Water Tower near Prison
(0.20\'/18m, sigma 32.5m) -> APPLIED, Interchange intact 0.001\'. Bonus: 6
retriangulations qui ecrasaient silencieusement des observers maintenant en
review (Brickell Arch all-obs 432\'!). Idempotent."""
import base64, json, sys

PAYLOAD_B64 = "eyJjb21tb25fYmxvY2siOiAiX0NPVl9DQUNIRSA9IE5vbmVcblxuZGVmIGxtX3NpZ21hX20obG1fbmFtZSk6XG4gICAgXCJcIlwiU2lnbWEgKG0sIG5vcm1lIHh5eikgZHUgTE0gZGVwdWlzIGxlIGRlcm5pZXIgY292YXJpYW5jZXMuanNvbiBkdSBCQVxuICAgIFtDT1ZBUklBTkNFLVYxXS4gTm9uZSBzaSBsZSBMTSBuJ2V0YWl0IHBhcyBkYW5zIGxlIHNvbHZlIG91IHBhcyBkZSBmaWNoaWVyLlxuICAgIFVzYWdlIGdhdGVzOiBkZWx0YSBzdGF0aXN0aXF1ZW1lbnQgaW5zaWduaWZpYW50IHNpIGRlbHRhIDw9IDMqc2lnbWEuXCJcIlwiXG4gICAgZ2xvYmFsIF9DT1ZfQ0FDSEVcbiAgICBpZiBfQ09WX0NBQ0hFIGlzIE5vbmU6XG4gICAgICAgIHRyeTpcbiAgICAgICAgICAgIGltcG9ydCBvcyBhcyBfb3NcbiAgICAgICAgICAgIHAgPSBfb3MucGF0aC5qb2luKF9vcy5wYXRoLmRpcm5hbWUoX29zLnBhdGguYWJzcGF0aChfX2ZpbGVfXykpLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgJ2dlbmVyYXRlZCcsICdjb3ZhcmlhbmNlcy5qc29uJylcbiAgICAgICAgICAgIF9DT1ZfQ0FDSEUgPSBqc29uLmxvYWQob3BlbihwKSkuZ2V0KCdsbXMnLCB7fSlcbiAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbjpcbiAgICAgICAgICAgIF9DT1ZfQ0FDSEUgPSB7fVxuICAgIGUgPSBfQ09WX0NBQ0hFLmdldChsbV9uYW1lKVxuICAgIHJldHVybiBOb25lIGlmIGUgaXMgTm9uZSBlbHNlIGUuZ2V0KCdzaWdtYV9tJylcblxuXG4iLCAiaGFydmVzdF9wYWlycyI6IFtbIiAgICBkbCA9IHJlLnNlYXJjaChyJ0RlbHRhIGZyb20gY3VycmVudDogKFtcXGQuXSspJywgci5zdGRvdXQpIiwgIiAgICBkbCA9IHJlLnNlYXJjaChyJ0RlbHRhIGZyb20gY3VycmVudDogKFtcXGQuXSspJywgci5zdGRvdXQpXG4gICAgYW8gPSByZS5zZWFyY2gocidBbGwtb2JzZXJ2ZXIgcmVzaWR1YWw6IG1heCAoW1xcZC5dKyknLCByLnN0ZG91dCkiXSwgWyIgICAgICAgIG9rID0gbXh2IDwgOCBhbmQgKGtpbmQgPT0gJ3RyaScgb3IgKGRsdiBpcyBub3QgTm9uZSBhbmQgZGx2IDwgMTUpKSIsICIgICAgICAgICMgU0lHTUEtR0FURVMtVjE6IGxhIGdhdGUgZGVsdGEgZGV2aWVudCByZWxhdGl2ZSBhIGwnaW5jZXJ0aXR1ZGUgZHVcbiAgICAgICAgIyBMTSAoQ09WQVJJQU5DRS1WMSk6IHVuIG1vdmUgPD0gMypzaWdtYSBlc3Qgc3RhdGlzdGlxdWVtZW50XG4gICAgICAgICMgaW5zaWduaWZpYW50IG1lbWUgcydpbCBkZXBhc3NlIDE1bSAoZXg6IFdhdGVyIFRvd2VyIG5lYXIgUHJpc29uXG4gICAgICAgICMgMThtIGF2ZWMgc2lnbWE9MzIuNW0pLiBQbGFuY2hlciAxNSBjb25zZXJ2ZSBwb3VyIGxlcyBMTSBob3JzIHNvbHZlLlxuICAgICAgICB0cnk6XG4gICAgICAgICAgICBzeXMucGF0aC5pbnNlcnQoMCwgJ3Rvb2xzJylcbiAgICAgICAgICAgIGZyb20gY29tbW9uIGltcG9ydCBsbV9zaWdtYV9tXG4gICAgICAgICAgICBfc2lnID0gbG1fc2lnbWFfbShsbSlcbiAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbjpcbiAgICAgICAgICAgIF9zaWcgPSBOb25lXG4gICAgICAgIGdhdGVfZCA9IG1heCgxNS4wLCAzLjAgKiBfc2lnKSBpZiBfc2lnIGlzIG5vdCBOb25lIGVsc2UgMTUuMFxuICAgICAgICAjIE9CU0VSVkVSLUdVQVJELVYxIChyZWdsZSBGbGFnbGVyIGVuIGNvZGUpOiBsZSBwb2ludCBwcm9wb3NlIGRvaXRcbiAgICAgICAgIyBzYXRpc2ZhaXJlIFRPVVMgbGVzIG9ic2VydmVycyBub24tZXhjbHVzICg8OCcpLCBwYXMganVzdGUgbGUgcG9vbC5cbiAgICAgICAgYW92ID0gZmxvYXQoYW8uZ3JvdXAoMSkpIGlmIGFvIGVsc2UgTm9uZVxuICAgICAgICBvYnNfb2sgPSAoYW92IGlzIE5vbmUpIG9yIChhb3YgPCA4KVxuICAgICAgICBvayA9IG14diA8IDggYW5kIG9ic19vayBhbmQgKGtpbmQgPT0gJ3RyaScgb3IgKGRsdiBpcyBub3QgTm9uZSBhbmQgZGx2IDwgZ2F0ZV9kKSkiXSwgWyIgICAgICAgICAgICBzdGF0ZVsncmV2aWV3J10uYXBwZW5kKChraW5kLCBsbSwgbXh2LCBkbHYpKSIsICIgICAgICAgICAgICB3aHlfcmV2ID0gZidhbGwtb2JzIHthb3Y6LjFmfScgaWYgKGFvdiBpcyBub3QgTm9uZSBhbmQgYW92ID49IDgpIGVsc2UgZidkZWx0YSB7ZGx2fSdcbiAgICAgICAgICAgIHN0YXRlWydyZXZpZXcnXS5hcHBlbmQoKGtpbmQsIGxtLCBteHYsIGRsdiwgd2h5X3JldikpIl1dLCAic2Nhbl9wYWlyIjogWyIgICAgICAgIGlmIHJlc2lkIDwgR0FURV9SRVNJRCBhbmQgZGVsdGEgPCBHQVRFX0RFTFRBOiIsICIgICAgICAgIF9zaWcgPSBOb25lXG4gICAgICAgIHRyeTpcbiAgICAgICAgICAgIGZyb20gY29tbW9uIGltcG9ydCBsbV9zaWdtYV9tXG4gICAgICAgICAgICBfc2lnID0gbG1fc2lnbWFfbShsbSlcbiAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbjpcbiAgICAgICAgICAgIHBhc3NcbiAgICAgICAgZ2F0ZV9kID0gbWF4KEdBVEVfREVMVEEsIDMuMCAqIF9zaWcpIGlmIF9zaWcgaXMgbm90IE5vbmUgZWxzZSBHQVRFX0RFTFRBXG4gICAgICAgIGlmIHJlc2lkIDwgR0FURV9SRVNJRCBhbmQgZGVsdGEgPCBnYXRlX2Q6ICAjIFNJR01BLUdBVEVTLVYxIl0sICJ0cmlfcGFpciI6IFsiICAgIHByaW50KGZcIlRyaWFuZ3VsYXRpb24gcmVzdWx0OlwiKSIsICIgICAgIyBPQlNFUlZFUi1HVUFSRC1WMSAoMjAyNi0wNy0wNywgcmVnbGUgRmxhZ2xlciBFTiBDT0RFKTogcmVzaWR1cyBkZSBUT1VTXG4gICAgIyBsZXMgb2JzZXJ2ZXJzIG5vbi1leGNsdXMgYXUgcG9pbnQgZmluYWwgXHUyMDE0IHBhcyBqdXN0ZSBsZSBwb29sIHJldGVudS4gTGVcbiAgICAjIHBvb2wgcGV1dCBlY2FydGVyIHNpbGVuY2lldXNlbWVudCB1biBvYnNlcnZlciBzYWluIChGbGFnbGVyOiBwb29sXG4gICAgIyBHcmFzc3JpdmVycytTa3lsaW5lIHByb3Bvc2UgdW4gcG9pbnQgcXVpIG1ldCBJbnRlcmNoYW5nZSAwLjAnLT4yMS44JykuXG4gICAgYWxsX29icyA9IFtjIGZvciBjIGluIG9ic2VydmVyc19jbGFzc2lmaWVkXG4gICAgICAgICAgICAgICBpZiBvYnNlcnZlcnNfY2xhc3NpZmllZFtjXSAhPSAnZXhjbHVkZWQnXVxuICAgIGFsbF9yYXlzID0gX2J1aWxkX3JheXMoYWxsX29icywgYXJncy5sbV9uYW1lLCBwaXhlbHMpXG4gICAgYWxsX3JlcyA9IF9yZXNpZHVhbHNfYXJjbWluKG5ld194eXosIGFsbF9yYXlzKVxuICAgIGFsbF9tYXggPSBtYXgoYWxsX3Jlcy52YWx1ZXMoKSkgaWYgYWxsX3JlcyBlbHNlIE5vbmVcbiAgICBpZiBhbGxfcmVzOlxuICAgICAgICB3b3JzdF9jYW0gPSBtYXgoYWxsX3Jlcywga2V5PWFsbF9yZXMuZ2V0KVxuICAgICAgICBwcmludChmXCJBbGwtb2JzZXJ2ZXIgcmVzaWR1YWw6IG1heCB7YWxsX21heDouM2Z9IGFyY21pbiBcIlxuICAgICAgICAgICAgICBmXCIoe2xlbihhbGxfcmVzKX0gb2JzLCB3b3JzdDoge3dvcnN0X2NhbX0pXCIpXG5cbiAgICBwcmludChmXCJUcmlhbmd1bGF0aW9uIHJlc3VsdDpcIikiXX0="
P = json.loads(base64.b64decode(PAYLOAD_B64))

def patch(path, fn):
    src = open(path).read()
    out, msg = fn(src)
    if out is None:
        print(f'ok  {path}: {msg}')
        return
    open(path, 'w').write(out)
    print(f'EDIT {path}: {msg}')

def f_common(src):
    if 'lm_sigma_m' in src:
        return None, 'deja patche'
    a = 'def residual_dual(cam, mk, xyz):'
    assert a in src, 'ancre residual_dual introuvable (DUAL-METRIC requis)'
    return src.replace(a, P['common_block'] + a, 1), 'lm_sigma_m ajoute'

def f_harvest(src):
    if 'SIGMA-GATES-V1' in src:
        return None, 'deja patche'
    for old, new in P['harvest_pairs']:
        assert old in src, 'ancre harvest introuvable: ' + old[:50]
        src = src.replace(old, new, 1)
    return src, 'sigma-gate + observer-guard'

def f_scan(src):
    if 'SIGMA-GATES-V1' in src:
        return None, 'deja patche'
    old, new = P['scan_pair']
    assert old in src, 'ancre collision_scan introuvable'
    return src.replace(old, new, 1), 'sigma-gate'

def f_tri(src):
    if 'OBSERVER-GUARD-V1' in src:
        return None, 'deja patche'
    old, new = P['tri_pair']
    assert old in src, 'ancre triangulate introuvable'
    return src.replace(old, new, 1), 'all-observer residual'

patch('tools/common.py', f_common)
patch('harvest_run.py', f_harvest)
patch('tools/audit/collision_scan.py', f_scan)
patch('tools/triangulate_lm.py', f_tri)
print('\nSIGMA-GATES-V1 + OBSERVER-GUARD-V1 en place.')
