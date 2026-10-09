#!/usr/bin/env python3
"""gtadb_meshes.py — batiments IDENTIFIES par GTADB, plan V16, hauteur IRL (OSM). [GTADB-MESH-V1 2026-10-08]

Regle de hauteur du projet: >= 1 point triangule, sinon IRL si le secteur suit l'IRL (ratio verifie, source notee).
Ratio jeu/IRL mesure sur 40 meshes deja mesures: mediane 1.04, IQR 0.91-1.24 -> Vice City / Vice Beach suivent l'IRL.
Identification: les lieux GTADB (GTA VI Landmarks Data, CC BY 4.0, https://map.gtadb.org, via map.stateofleonida.net)
donnent pour chaque batiment du jeu sa position (repere du jeu = le notre, verifie a 5-18 m) et son equivalent IRL (adresse,
lat/lon). Hauteur = OSM (tools/generated/osm_miami_buildings.json) du batiment IRL (le plus proche de la lat/lon, < 25 m).
Plan = emprise V16 qui contient le point GTADB (ou la plus proche a < 12 m); si la V16 dessine des regions interieures
et que celle du point a une aire compatible avec l'empreinte OSM (x0.35-2.5), la TOUR = cette region (hauteur IRL) et le
reste de la parcelle = podium 12 m ESTIME; sinon la parcelle entiere.
Noms: le mesh porte le nom EN JEU s'il est connu (sinon le nom IRL), et toujours les deux (name_game / name_irl).
Apres generation: filtre (point sur/pres d'un volume existant, nom IRL deja modelise, un seul brouillon par parcelle V16) puis
validation dans les cams fiables (rejet si le mesh perce le ciel ou si ses aretes contredisent la frame) — voir le commit.
Exclus: points a < 25 m d'un mesh existant, hauteur IRL < 8 m, parcelle < 80 m2, tags parc/naturel/transport.
Sortie: brouillons tools/generated/gtadb_meshes_draft.json (+ rapport). --apply ecrit dans building_meshes_procedural.json.
Usage: python3 tools/gtadb_meshes.py [--bbox X0 Y0 X1 Y1] [--only L123,L456] [--apply]
"""
import json, os, sys, math, shutil
import numpy as np, cv2
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import mesh_solids as MS
from horizon_resect import ground

GT = os.path.join(THIS, 'generated', 'gtadb_locations.json')
OSM = os.path.join(THIS, 'generated', 'osm_miami_buildings.json')
OUT = os.path.join(THIS, 'generated', 'gtadb_meshes_draft.json')
MESHES = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
SKIP_TAGS = {'natural', 'transportation', 'public', 'events', 'landmark', 'utilities', 'demolished', 'construction'}
RATIO = (1.04, 0.91, 1.24)


def osm_index():
    O = json.load(open(OSM))['elements']; out = []
    for e in O:
        if e.get('type') != 'way' or 'geometry' not in e: continue
        t = e.get('tags', {}); hh = None
        for k in ('height', 'building:height'):
            if t.get(k):
                try: hh = float(str(t[k]).replace('m', '').split(';')[0].strip()); break
                except Exception: pass
        if hh is None and t.get('building:levels'):
            try: hh = float(t['building:levels']) * 3.2
            except Exception: pass
        if hh is None: continue
        P = np.array([[g['lon'], g['lat']] for g in e['geometry']], float)
        out.append((P, hh, t.get('name', ''), e['id']))
    return out


def osm_at(OI, lat, lon):
    best = None
    for P, hh, nm, oid in OI:
        if not (P[:, 1].min() - 0.0004 < lat < P[:, 1].max() + 0.0004 and P[:, 0].min() - 0.0004 < lon < P[:, 0].max() + 0.0004): continue
        ins = cv2.pointPolygonTest(P.astype(np.float32).reshape(-1, 1, 2), (lon, lat), True)
        d = 0.0 if ins >= 0 else -ins * 111000
        if d < 25 and (best is None or (d, -hh) < (best[0], -best[1])):
            # aire (m2) approx
            xy = np.c_[(P[:, 0] - P[0, 0]) * 111000 * math.cos(math.radians(lat)), (P[:, 1] - P[0, 1]) * 111000]
            a = abs(np.sum(xy[:, 0] * np.roll(xy[:, 1], 1) - np.roll(xy[:, 0], 1) * xy[:, 1])) / 2
            best = (d, hh, nm, oid, a)
    return best


def main():
    bb = [float(v) for v in sys.argv[sys.argv.index('--bbox') + 1:sys.argv.index('--bbox') + 5]] if '--bbox' in sys.argv else None
    only = set(sys.argv[sys.argv.index('--only') + 1].split(',')) if '--only' in sys.argv else None
    G = json.load(open(GT)); F = json.load(open(os.path.join(REPO, 'gtamapdata', 'v16_footprints.json')))['polygons']
    S = MS.build(); cent = np.array([np.mean([q for L in so['layers'] for p in L['polys'] for q in p['outer']], axis=0) for so in S.values() if so['layers']])
    Fc = np.array([f['centroid'] for f in F]); OI = osm_index(); M = json.load(open(MESHES))
    import v16_tiers as VT
    drafts = {}; rep = []
    for key, e in G.items():
        if only and key not in only: continue
        if not isinstance(e, list) or len(e) < 7 or not e[1] or len(e[1]) < 2 or not e[4]: continue
        x, y = e[1]; tags = set(e[6] or [])
        if bb and not (bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3]): continue
        if tags & SKIP_TAGS: continue
        if len(cent) and np.min(np.hypot(cent[:, 0] - x, cent[:, 1] - y)) < 25: continue
        irl = e[3].split(',')[0]; game = e[0].split(',')[0]
        name = (game if game not in ('?', '') and not game.startswith('?') else irl).strip()
        if not name or name in M: continue
        # emprise V16
        near = np.where(np.hypot(Fc[:, 0] - x, Fc[:, 1] - y) < 150)[0]; pid = None; best = None
        for i in near:
            R = np.array(F[i]['ring'], np.float32); d = cv2.pointPolygonTest(R.reshape(-1, 1, 2), (float(x), float(y)), True)
            if d >= -12 and F[i]['area'] >= 80 and (best is None or d > best): best, pid = d, i
        if pid is None: rep.append((key, name, 'pas d emprise V16')); continue
        oh = osm_at(OI, *e[4])
        if not oh or oh[1] < 8: rep.append((key, name, 'pas de hauteur OSM >= 8 m')); continue
        hh = round(oh[1], 1); R = np.array(F[pid]['ring'], float); g = float(ground(*R.mean(0)))
        tower = None
        try:
            regs = VT.regions(pid)
            if len(regs) > 1:
                for rg in regs:
                    rr = np.array(rg['ring'], np.float32)
                    if cv2.pointPolygonTest(rr.reshape(-1, 1, 2), (float(x), float(y)), True) >= -3 and 0.35 <= rg['area'] / max(oh[4], 1) <= 2.5: tower = rg; break
        except Exception: regs = []
        E = []
        def seg(a, b): E.append([[round(float(v), 2) for v in a], [round(float(v), 2) for v in b]])
        def prism(ring, z0, z1):
            for k in range(len(ring)):
                a, b = ring[k], ring[(k + 1) % len(ring)]
                seg([*a, z0], [*b, z0]); seg([*a, z1], [*b, z1]); seg([*a, z0], [*a, z1])
        if tower is not None and hh > 18:
            prism(R.tolist(), g, g + 12.0); prism(tower['ring'], g + 12.0, g + hh)
            plan = 'tower = V16 region %d of lot %d (%.0f m2, OSM footprint %.0f m2), podium 12 m ESTIMATED' % (tower['id'], pid, tower['area'], oh[4])
        else:
            prism(R.tolist(), g, g + hh); plan = 'whole V16 lot %d (%.0f m2, OSM footprint %.0f m2)' % (pid, F[pid]['area'], oh[4])
        gname = game if game and not game.startswith('?') else None
        drafts[name] = {'color': '#cbd5e1', 'world_edges': E, 'name_game': gname, 'name_irl': irl, '_credit': 'identification: GTA VI Landmarks Data (CC BY 4.0) https://map.gtadb.org; plan: V16; height: OpenStreetMap (ODbL)',
                        'note': ('GTADB-MESH-V1 2026-10-08: %s (GTADB %s = IRL %s). %s. Height %.1f m = IRL (OpenStreetMap way %s%s), game/IRL height ratio checked on 40 measured meshes: median %.2f, IQR %.2f-%.2f. Ground %.1f (heightmap).'
                                 % (name, key, irl, plan, hh, oh[3], (' "' + oh[2] + '"') if oh[2] else '', RATIO[0], RATIO[1], RATIO[2], g)),
                        '_gtadb': key, '_v16': int(pid), '_h': hh}
        rep.append((key, name, 'OK h %.1f, %s' % (hh, plan)))
    json.dump(drafts, open(OUT, 'w'), indent=1, ensure_ascii=True)
    ok = [r for r in rep if r[2].startswith('OK')]
    for r in ok: print(r)
    print('%d brouillons (%d lieux examines) -> %s' % (len(drafts), len(rep), OUT))
    if '--apply' in sys.argv and drafts:
        shutil.copy(MESHES, MESHES + '.bak_gtadb_1008'); M = json.load(open(MESHES))
        for n, d in drafts.items():
            if n not in M: M[n] = {k: v for k, v in d.items() if not k.startswith('_') or k == '_credit'}
        json.dump(M, open(MESHES, 'w'), indent=1, ensure_ascii=True); print('applique ->', len(M))


if __name__ == '__main__':
    main()
