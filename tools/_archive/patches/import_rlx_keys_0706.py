#!/usr/bin/env python3
"""import_rlx_keys_0706.py -- import rlx 2026-07-06 markings.
Dry-run par defaut. --apply pour ecrire. Idempotent. Backups .bak_rlx_keys.
IMPORTE: 12 Islands B-E + 8 pts Jason House + snaps sub-pixel + corrections
Boat Ramp NW/SW + Empty Lot Ambrosia Hill TW/TE.
EXCLU: pillar renumber (nos 7/8/9 = ses 9/11/11), House with Boat (collision
de nom, 67.2 deg), Viaduct z prior. Seeding Islands GATE (pose non ancree)."""
import argparse, json, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

CAM_JASON = "Jason's Safehouse Vehicles (X)"
CAM_EMPTY = "Empty Lot near Metro Station"

ISLANDS = {
    "Island B (1)": [0.0, 1065.0], "Island B (2)": [213.5, 1062.5],
    "Island B (3)": [339.5, 1060.5], "Island C (1)": [865.0, 1044.5],
    "Island C (2)": [921.5, 1046.5], "Island C (3)": [1057.0, 1047.0],
    "Island C (4)": [1194.5, 1044.5], "Island D (1)": [2050.0, 1054.0],
    "Island E (1)": [3130.5, 1056.0], "Island E (2)": [3222.0, 1066.5],
    "Island E (3)": [3540.0, 1070.5], "Island E (4)": [3617.0, 1069.0],
}
RLX_ISLAND_XYZ = {
    "Island B (1)": (-2518.877, -5470.360), "Island B (2)": (-2514.199, -5461.703),
    "Island B (3)": (-2512.213, -5455.938), "Island C (1)": (-2517.450, -5419.032),
    "Island C (2)": (-2510.675, -5419.778), "Island C (3)": (-2503.078, -5415.444),
    "Island C (4)": (-2500.853, -5406.435), "Island D (1)": (-2445.936, -5390.611),
    "Island E (1)": (-2395.473, -5357.136), "Island E (2)": (-2386.001, -5372.459),
    "Island E (3)": (-2371.781, -5369.169), "Island E (4)": (-2369.228, -5364.479),
}
JASON_NEW = {
    "Jason's House (Boat Ramp) (S)": [3840.0, 1444.0],
    "Jason's House (Boat Ramp) (SW2)": [3255.0, 1393.5],
    "Jason's House (Garden Table) (BC)": [1178.0, 1248.0],
    "Jason's House (Pillar 5) (BNE)": [1472.0, 1383.5],
    "Jason's House (Pillar 5) (BSE)": [1427.0, 1389.0],
    "Jason's House (Pillar 5) (BSW)": [1383.5, 1379.0],
    "Jason's House (Pillar 6) (BSW)": [1854.0, 1341.0],
    "Jason's House (Roof) (BSE)": [1688.0, 309.0],
}
JASON_MOVES = {
    "Jason's House (Boat Ramp) (NW)": [3634.0, 1294.5],
    "Jason's House (Boat Ramp) (SW)": [3304.0, 1404.0],
    "Homestead Water Tower": [3410.0, 863.5],
    "Jason's House (Basketball Hoop) (BN)": [2596.0, 1042.5],
    "Jason's House (Basketball Hoop) (BS)": [2480.5, 1048.5],
    "Jason's House (Basketball Hoop) (TN)": [2596.5, 905.0],
    "Jason's House (Front Door) (TE)": [1290.5, 467.0],
    "Jason's House (Front Door) (TW)": [1146.5, 484.0],
    "Jason's House (Front Stairs) (MTNE)": [2192.0, 932.5],
    "Jason's House (Front Stairs) (MTSE)": [2068.5, 929.5],
    "Jason's House (Main) (BNE)": [2699.5, 889.0],
    "Jason's House (Main) (TNE)": [2705.5, 543.0],
    "Jason's House (Main) (TSE)": [1697.0, 316.5],
    "Jason's House (Main) (TSW)": [756.5, 429.5],
    "Jason's House (North Veranda) (TNE)": [3077.5, 908.0],
    "Jason's House (Pillar 1) (BSE)": [2664.0, 1408.5],
    "Jason's House (Pillar 1) (BSW)": [2605.5, 1403.0],
    "Jason's House (Power Pole) (T)": [3050.0, 496.5],
    "Jason's House (Rear Stairs) (BW)": [1600.5, 1212.0],
    "Jason's House (Roof) (NE)": [2779.0, 501.5],
    "Jason's House (Roof) (S)": [1113.0, 127.5],
    "Jason's House (South Veranda) (TNE)": [1796.0, 619.5],
    "Jason's House (South Veranda) (TSE)": [1548.0, 598.5],
    "Jason's House (South Veranda) (TSW)": [189.5, 712.0],
    "Jason's House (Upper Veranda) (TNE)": [2857.5, 776.0],
    "Jason's House (Window 1) (TW)": [861.5, 516.5],
    "Jason's House (Window 2) (TW)": [1418.0, 449.5],
    "Jason's House (Window 3) (BN)": [1953.5, 689.5],
    "Jason's House (Window 3) (TN)": [1954.0, 461.5],
    "Jason's House (Window 3) (TS)": [1847.0, 442.5],
    "Jason's House (Window 4) (BN)": [2313.5, 726.0],
    "Jason's House (Window 4) (BS)": [2236.5, 719.5],
    "Jason's House (Window 4) (TN)": [2316.5, 528.5],
    "Jason's House (Window 4) (TS)": [2237.5, 514.0],
    "Jason's House (Window 5) (BN)": [2591.5, 751.5],
    "Jason's House (Window 5) (BS)": [2481.5, 742.0],
    "Jason's House (Window 5) (TN)": [2593.5, 581.0],
    "Jason's House (Window 5) (TS)": [2481.0, 557.5],
}
EMPTY_LOT = {
    "Ambrosia Hill (TW)": [2998.0, 473.5],
    "Ambrosia Hill (TE)": [3192.0, 474.5],
}
SEED_GATE_M = 25.0


def jdump(obj, path):
    with open(path, 'w') as f:
        json.dump(obj, f, indent=2, ensure_ascii=True)
        f.write('\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    A = args.apply
    print(('=== APPLY ===' if A else '=== DRY-RUN (use --apply) ===') + '\n')

    px = json.load(open('gtamapdata/pixels.json'))
    lms = json.load(open('gtamapdata/landmarks.json'))
    n_add = n_move = n_skip = n_lm = 0

    jp = px[CAM_JASON]
    for lm, p in {**ISLANDS, **JASON_NEW}.items():
        if lm in jp:
            if jp[lm] == p:
                n_skip += 1
            else:
                print(f'??  {lm} deja present a {jp[lm]} != rlx {p} -- non touche')
            continue
        print(f'ADD  {CAM_JASON} :: {lm} @ {p}')
        jp[lm] = p
        n_add += 1
    for lm, p in JASON_MOVES.items():
        if lm not in jp:
            print(f'??  MOVE cible absente: {lm} -- skip')
            continue
        if jp[lm] == p:
            n_skip += 1
            continue
        d = ((jp[lm][0]-p[0])**2 + (jp[lm][1]-p[1])**2) ** 0.5
        print(f'MOVE {lm}: {jp[lm]} -> {p}  ({d:.1f}px)')
        jp[lm] = p
        n_move += 1

    ep = px.setdefault(CAM_EMPTY, {})
    for lm, p in EMPTY_LOT.items():
        if lm in ep:
            n_skip += 1
            continue
        print(f'ADD  {CAM_EMPTY} :: {lm} @ {p}')
        ep[lm] = p
        n_add += 1

    for lm in list(ISLANDS) + list(JASON_NEW) + list(EMPTY_LOT):
        if lm in lms:
            continue
        zone = 'ambrosia' if lm.startswith('Ambrosia') else 'leonida_keys'
        lms[lm] = {"xyz": None, "source_cameras": [], "error_m": None,
                   "zone": zone, "author": "rlx"}
        print(f'LM   create skeleton: {lm} (zone {zone})')
        n_lm += 1

    print('\n--- Seeding Islands (ray z=0, notre pose) ---')
    import gtamapdata as md_mod  # noqa
    import gtamaplib as ml
    cam = ml.get_camera(CAM_JASON)
    worst = 0.0
    for lm, p in ISLANDS.items():
        pt = cam.get_point_at_zero_elevation(p)
        rx, ry = RLX_ISLAND_XYZ[lm]
        d = ((pt[0]-rx)**2 + (pt[1]-ry)**2) ** 0.5
        worst = max(worst, d)
        flag = 'OK ' if d < SEED_GATE_M else '!!GATE'
        print(f'  {flag} {lm}: ours=({pt[0]:.1f},{pt[1]:.1f},0.0)  rlx=({rx},{ry})  delta={d:.1f}m')
        if d < SEED_GATE_M:
            lms[lm]['xyz'] = [round(pt[0], 3), round(pt[1], 3), 0.0]
            lms[lm]['source_cameras'] = [CAM_JASON]
        else:
            print(f'      -> xyz NON seede (gate {SEED_GATE_M}m), marking importe quand meme')
    print(f'  worst delta vs rlx: {worst:.1f}m')

    print(f'\nTotal: +{n_add} markings, {n_move} moves, {n_lm} LM crees, {n_skip} deja a jour')

    if A:
        import shutil
        shutil.copy('gtamapdata/pixels.json', 'gtamapdata/pixels.json.bak_rlx_keys')
        shutil.copy('gtamapdata/landmarks.json', 'gtamapdata/landmarks.json.bak_rlx_keys')
        jdump(px, 'gtamapdata/pixels.json')
        jdump(lms, 'gtamapdata/landmarks.json')
        print('ECRIT: pixels.json, landmarks.json (backups .bak_rlx_keys)')
    else:
        print('DRY-RUN: rien ecrit.')


if __name__ == '__main__':
    main()
