# Global multi-view solve (MVS-V1)

Cameras (non-SOLVED) and mesh footprints/heights solved together against the pose-audit edges of all day frames and the landmark markings. Residuals in sigma units. Nothing applied unless guarded --apply.

- before: {'edge_rms_sigma': 3.769, 'edge_med_abs': 1.186, 'lm_rms_sigma': 3.029}
- after: {'edge_rms_sigma': 3.19, 'edge_med_abs': 0.921, 'lm_rms_sigma': 2.922}

## Cameras (largest changes first)

| Camera | dx dy dz (m) | dyaw dpitch droll dfov (deg) | edges | LMs | edge rms | LM rms |
|---|---|---|---|---|---|---|
| Biplane (Video) v2811 | +1.3 -4.8 +5.2 | +1.47 -2.37 +0.58 -3.96 | 8 | 4 | 8.83 -> 3.48 | 0.92 -> 1.36 |
| Biplane (Video) v1080 | +2.1 +24.4 +4.0 | -1.75 -0.10 -0.45 +2.29 | 6 | 5 | 8.12 -> 2.59 | 0.43 -> 1.28 |
| Gas Station (Chase) (S) | -29.7 +2.9 +0.4 | +1.13 -0.06 -0.33 +1.79 | 6 | 5 | 7.94 -> 5.56 | 0.37 -> 0.84 |
| Boat | -0.3 +22.2 +5.2 | +0.38 +0.45 +0.18 -2.67 | 7 | 1 | 4.63 -> 1.52 | 0.51 -> 0.35 |
| Biplane (Video) v1980 | -16.4 -23.3 -0.1 | -0.47 +0.05 -0.16 -1.58 | 13 | 6 | 3.8 -> 3.04 | 0.91 -> 1.1 |
| Vice City Sign | +1.7 +22.9 -0.1 | -0.49 -0.12 +0.51 -0.40 | 5 | 0 | 6.72 -> 4.47 | None -> None |
| Biplane (Video) v2370 | +7.3 +11.3 +3.1 | +1.12 -0.39 +0.31 -0.35 | 0 | 7 | None -> None | 5.6 -> 5.42 |
| Oceanarium | +1.4 +10.7 +2.2 | +0.35 -0.29 -0.65 +0.33 | 35 | 0 | 4.2 -> 3.81 | None -> None |
| Biplane (Video) v0900 | -17.1 -8.4 +2.8 | -0.04 -0.04 -0.02 -0.65 | 17 | 13 | 2.88 -> 2.62 | 1.84 -> 1.91 |
| House (Keys) | +0.6 -0.9 +0.0 | -0.51 -0.40 +0.04 -1.91 | 0 | 31 | None -> None | 0.81 -> 0.58 |
| Speaking with Brian at Effluvia (2) | +2.5 +16.2 -3.5 | +0.14 +0.20 +0.11 -0.75 | 25 | 0 | 2.91 -> 1.13 | None -> None |
| Speaking with Brian at Effluvia (3) | +2.1 +10.8 -5.9 | +0.01 +0.23 +0.09 -0.35 | 39 | 0 | 2.72 -> 1.95 | None -> None |
| Vintage Vice City Pack 02 (Port) | -5.2 +1.0 -6.4 | -0.23 +0.31 -0.04 +0.01 | 4 | 0 | 3.66 -> 0.37 | None -> None |
| Biplane (Video) v3000 | -3.1 -3.0 +0.4 | -0.47 +0.12 +0.07 -1.40 | 8 | 5 | 3.1 -> 2.58 | 1.65 -> 1.91 |
| '95 Grotti Cheetah 04 (Garage) | +4.8 +1.9 +0.4 | -0.13 -0.01 -0.49 +0.24 | 1 | 4 | 4.5 -> 1.15 | 0.34 -> 0.52 |
| Biplane (Video) v2580 | -5.8 -6.5 -1.1 | +0.36 +0.33 +0.07 -0.88 | 27 | 10 | 6.52 -> 4.29 | 3.0 -> 3.61 |
| Raul Bautista 03 (Motorboat) | +0.1 -10.7 -2.2 | +0.08 +0.23 +0.09 -0.72 | 6 | 9 | 5.86 -> 3.17 | 1.13 -> 1.6 |
| Biplane (Video) v1380 | +4.1 +4.8 -0.4 | -0.41 -0.03 +0.10 +0.94 | 17 | 6 | 1.82 -> 1.32 | 2.12 -> 2.09 |
| Starlet Motel | -0.2 -1.8 -0.1 | -0.38 -0.10 +0.03 -1.18 | 0 | 7 | None -> None | 14.97 -> 14.65 |
| Amphitheater | -0.1 +6.4 +3.1 | -0.33 -0.28 -0.05 +0.46 | 6 | 6 | 5.58 -> 4.93 | 2.03 -> 1.91 |
| Speaking with Brian at Effluvia (1) | -1.3 -3.6 +0.5 | +0.19 -0.09 +0.35 -0.37 | 19 | 0 | 2.9 -> 2.45 | None -> None |
| Street (Bikers) (B) | +0.4 +8.9 -0.9 | -0.29 -0.04 -0.04 +0.60 | 2 | 7 | 5.9 -> 0.05 | 0.95 -> 0.88 |
| Highway (Peacock Bay) (A) | +1.0 +5.4 +0.2 | -0.22 -0.02 -0.05 +0.86 | 4 | 4 | 2.25 -> 2.71 | 3.14 -> 2.61 |
| Highway (Peacock Bay) (B) | -0.4 -1.4 +0.6 | -0.01 -0.08 +0.32 -0.31 | 12 | 10 | 4.98 -> 4.59 | 1.6 -> 1.62 |
| Yacht (1) | +0.6 -3.0 -0.5 | +0.09 +0.14 +0.31 -0.19 | 4 | 2 | 2.06 -> 1.72 | 0.47 -> 0.49 |
| Water Tower [Gameinformer] | +0.5 +2.6 -0.1 | +0.17 -0.03 -0.18 +0.74 | 12 | 0 | 1.94 -> 1.8 | None -> None |
| Shoreline [Gameinformer] | -2.8 -8.2 +0.6 | -0.01 -0.10 -0.01 +0.30 | 29 | 0 | 1.41 -> 1.57 | None -> None |
| Street (Jason) | -1.7 -1.6 -0.1 | -0.60 -0.04 -0.06 -0.07 | 3 | 0 | 3.27 -> 0.06 | None -> None |
| Character Switch in Vice Beach (A) | -0.5 -0.3 -1.7 | +0.17 -0.12 +0.23 +0.17 | 0 | 9 | None -> None | 6.77 -> 6.78 |
| Port Gellhorn 04 (Delights) (X) | +0.0 -0.7 -0.6 | -0.24 +0.22 -0.21 +0.02 | 0 | 4 | None -> None | 0.64 -> 0.54 |
| Prison (Video) v160 | +2.8 -1.1 +0.5 | -0.18 -0.07 -0.12 -0.45 | 0 | 4 | None -> None | 0.4 -> 0.27 |
| Interchange | +1.0 +2.3 -0.3 | +0.03 +0.01 +0.17 +0.10 | 2 | 4 | 2.06 -> 0.84 | 0.61 -> 0.65 |
| Street (Lucia) (N) | +3.5 -2.6 -0.6 | +0.13 -0.09 +0.01 +0.30 | 5 | 0 | 6.07 -> 0.16 | None -> None |
| Biplane (Video) v0820 | -3.3 -2.7 +1.0 | +0.07 -0.01 -0.07 -0.11 | 21 | 12 | 3.43 -> 3.19 | 2.97 -> 3.04 |
| Prison (Aerial) (Biplane) | +3.1 +0.9 +0.9 | +0.12 -0.08 +0.04 -0.31 | 0 | 8 | None -> None | 3.52 -> 3.51 |
| Sunrise over Vice City (Extended Look) | -4.7 +1.5 +1.0 | -0.02 -0.02 +0.02 -0.09 | 46 | 31 | 4.89 -> 4.02 | 2.18 -> 2.19 |
| Parachute Jump over Vice Beach (Extended Look) | +1.5 +0.1 -1.8 | -0.07 +0.10 -0.01 +0.04 | 27 | 5 | 2.5 -> 2.31 | 0.39 -> 0.46 |
| Biplane Night (Vice Beach) | +0.5 -1.7 +0.7 | +0.11 -0.06 +0.06 -0.28 | 0 | 7 | None -> None | 0.57 -> 0.49 |
| Grassrivers 02 (Watson Bay) | +0.0 +0.3 -1.8 | -0.01 +0.03 -0.02 +0.01 | 16 | 58 | 2.73 -> 2.52 | 4.96 -> 3.13 |
| Prison (Video) v250 | +2.7 -1.5 +0.9 | +0.15 -0.04 +0.02 -0.01 | 0 | 9 | None -> None | 2.26 -> 2.35 |
| Vice City Postcard | +0.0 -4.6 +0.2 | -0.06 -0.00 +0.03 +0.12 | 47 | 83 | 2.39 -> 1.98 | 1.82 -> 1.4 |
| Grassrivers Postcard (X) | -2.5 -2.9 -0.7 | +0.00 -0.00 +0.05 +0.04 | 0 | 6 | None -> None | 4.89 -> 4.87 |
| Grassrivers 05 (Sunrise RV Park) | -1.2 -3.7 -0.4 | +0.02 +0.01 +0.01 -0.00 | 24 | 35 | 4.03 -> 3.64 | 1.81 -> 1.82 |
| Port Vice City (A) | -3.1 -2.1 -0.4 | -0.04 +0.02 -0.02 +0.12 | 45 | 65 | 2.63 -> 2.17 | 0.77 -> 0.74 |
| Biplane Night (Video) Last | +0.4 -1.5 -0.2 | +0.09 -0.03 +0.07 -0.19 | 0 | 6 | None -> None | 2.49 -> 2.49 |
| Jason's Safehouse Vehicles (X) | +0.1 -0.1 -0.0 | +0.03 +0.07 +0.01 -0.34 | 0 | 43 | None -> None | 1.72 -> 1.48 |
| Prison (Video) f140 | -0.5 -0.2 +1.2 | -0.05 -0.12 -0.03 +0.03 | 0 | 8 | None -> None | 0.3 -> 0.26 |
| Prison (Video) v310 | +1.0 +1.2 -0.2 | +0.06 +0.01 -0.05 +0.19 | 17 | 14 | 4.05 -> 3.61 | 2.36 -> 2.37 |
| Prison (Video) f180 | +0.7 -1.4 +0.6 | -0.04 -0.04 -0.02 -0.15 | 0 | 8 | None -> None | 0.22 -> 0.2 |
| Vice City 03 (Basketball) | +2.0 +1.4 -0.3 | +0.03 +0.03 +0.03 -0.11 | 16 | 62 | 2.36 -> 2.29 | 1.57 -> 1.08 |
| Vice City 10 (Pegassi Towers) | +1.3 -0.7 -0.4 | -0.07 +0.05 -0.01 -0.15 | 26 | 23 | 2.43 -> 1.86 | 0.87 -> 0.93 |
| Yacht (2) | -1.0 -0.6 -0.4 | +0.03 +0.04 +0.03 -0.21 | 0 | 3 | None -> None | 1.1 -> 0.01 |
| Character Switch in Vice Beach (B) | +0.5 +0.6 -0.1 | +0.04 +0.13 -0.00 +0.05 | 0 | 6 | None -> None | 2.47 -> 2.52 |
| Convertible | -0.1 -0.0 +0.0 | -0.01 +0.01 -0.08 -0.06 | 5 | 22 | 4.54 -> 3.93 | 4.24 -> 4.11 |
| Jet Ski | -1.9 -0.3 +0.2 | -0.08 -0.01 +0.02 -0.01 | 18 | 20 | 2.89 -> 2.78 | 0.37 -> 0.44 |
| Landing Gear (B) | -0.6 +0.0 -0.3 | +0.04 +0.02 -0.06 -0.08 | 0 | 5 | None -> None | 0.42 -> 0.19 |
| Motorboats (A) | +0.2 -0.0 +0.0 | +0.01 -0.01 +0.08 -0.06 | 15 | 28 | 3.64 -> 3.73 | 0.74 -> 0.76 |
| Prison (Video) f100 | -0.5 +1.6 -0.1 | +0.04 -0.01 +0.01 +0.17 | 0 | 8 | None -> None | 0.31 -> 0.3 |
| Prison (Video) v091 (Wing) | -0.5 -1.0 +0.3 | -0.05 -0.04 -0.04 -0.14 | 13 | 12 | 3.46 -> 3.46 | 4.12 -> 4.13 |
| Skyline | -0.5 -0.9 -0.2 | -0.03 +0.01 -0.05 +0.12 | 50 | 56 | 2.33 -> 2.07 | 0.55 -> 0.59 |
| VCIA Night (Runway) | -1.2 -0.4 -0.7 | -0.01 +0.01 -0.01 +0.05 | 0 | 6 | None -> None | 0.98 -> 0.97 |
| Venetian Islands | -1.3 -0.6 +0.0 | -0.01 -0.01 -0.07 -0.00 | 42 | 64 | 2.64 -> 2.49 | 1.02 -> 0.88 |
| Vice City 11 (Megamundo) | +0.7 +0.6 +0.2 | +0.01 -0.02 -0.07 +0.09 | 25 | 22 | 3.81 -> 3.63 | 1.47 -> 1.48 |
| Chase (2) (A) | -0.0 -1.0 -0.0 | +0.03 +0.00 +0.00 -0.15 | 0 | 10 | None -> None | 4.54 -> 4.52 |
| Thunderstorm [Gameinformer] | +1.4 -0.6 +0.1 | -0.04 -0.06 +0.00 -0.05 | 7 | 0 | 1.75 -> 1.13 | None -> None |
| Vice Beach (A) | +1.5 -0.4 -0.4 | -0.04 +0.03 +0.03 -0.05 | 41 | 53 | 2.57 -> 2.17 | 1.59 -> 1.03 |
| Vice City 01 (Vice City Sign) | +0.1 -0.1 +0.0 | +0.02 +0.05 +0.01 +0.18 | 0 | 33 | None -> None | 1.02 -> 1.01 |
| Biplane (Video) v0770 | -0.5 -0.8 +0.3 | +0.03 -0.01 +0.01 -0.06 | 18 | 14 | 3.24 -> 3.19 | 2.86 -> 2.86 |
| Leonida Keys 05 (Boats) | +0.3 +0.4 +0.1 | -0.03 +0.02 +0.01 -0.14 | 0 | 13 | None -> None | 0.39 -> 0.37 |
| Prison | +0.8 +0.7 +0.4 | -0.02 -0.03 +0.02 +0.05 | 23 | 57 | 1.65 -> 1.13 | 3.21 -> 3.19 |
| Prison (Video) v500 | -0.0 +0.2 -0.1 | +0.01 +0.00 +0.05 +0.02 | 0 | 8 | None -> None | 0.94 -> 0.94 |
| Prison (Video) v600 | -0.1 -0.2 -0.3 | -0.01 +0.04 -0.04 +0.01 | 0 | 8 | None -> None | 1.22 -> 1.22 |
| Vice City 08 (Ferris Wheel) | -0.3 +1.2 -0.1 | -0.04 +0.03 +0.00 -0.03 | 2 | 43 | 7.43 -> 6.51 | 2.57 -> 2.51 |
| Chase (2) (B) | -0.0 +0.0 +0.0 | -0.01 -0.02 +0.04 +0.02 | 0 | 8 | None -> None | 5.5 -> 5.52 |
| Motorboats (B) | +0.1 -0.1 +0.2 | +0.01 -0.01 +0.02 -0.08 | 19 | 23 | 2.46 -> 2.46 | 0.74 -> 0.72 |
| Rooftop Party | +0.3 +0.8 +0.2 | +0.02 -0.01 +0.01 +0.05 | 31 | 33 | 4.64 -> 4.43 | 2.01 -> 2.02 |
| Shitzu Squalo 01 (Bay) | +0.5 -0.3 -0.0 | -0.03 -0.00 +0.02 +0.04 | 34 | 39 | 4.58 -> 4.45 | 0.99 -> 0.99 |
| Vintage Vice City Outfits and Hairstyles 04 (Rooftop) | -0.1 -0.5 +0.1 | -0.01 -0.00 -0.03 +0.01 | 0 | 5 | None -> None | 0.46 -> 0.46 |
| Throwing Stuff from an Overpass | +0.0 +0.6 -0.1 | -0.01 +0.01 -0.01 -0.03 | 2 | 26 | 5.5 -> 5.29 | 0.57 -> 0.58 |
| AI World Editor Map (4K) | +0.1 +0.0 -0.0 | -0.01 +0.00 +0.00 -0.00 | 0 | 70 | None -> None | 0.3 -> 0.3 |

## Meshes (largest changes first)

| Mesh | tx ty (m) | height scale | prior | cams | edge rms |
|---|---|---|---|---|---|
| 100 Biscayne Blvd (NE) | +6.3 +5.6 | -0.238 | estimated | 4 | 7.85 -> 6.61 |
| New Wave Condominiums | +4.8 -4.3 | -0.122 | estimated | 1 | 5.21 -> 1.04 |
| Icon Brickell | -6.2 +6.9 | -0.003 | estimated | 14 | 3.61 -> 3.1 |
| Met 1 | +3.0 +9.2 | +0.013 | measured | 1 | 5.83 -> 1.27 |
| South Pointe Tower | +0.6 -11.8 | -0.008 | measured | 5 | 6.83 -> 5.93 |
| The Grand | -6.0 -3.9 | +0.022 | estimated | 12 | 2.98 -> 2.47 |
| The Four Ambassadors | +3.0 +3.4 | -0.053 | measured | 1 | 4.13 -> 2.78 |
| 109 NE 2nd Ave | +0.8 +3.3 | -0.075 | measured | 2 | 4.77 -> 2.76 |
| 8 N Miami Ave | -4.8 +6.6 | +0.000 | measured | 2 | 7.03 -> 4.78 |
| The Bentley Bay South | -0.1 +10.8 | +0.003 | estimated | 3 | 2.74 -> 0.31 |
| Meditteranea Condo | -0.1 -0.0 | -0.106 | roof-anchored estimated | 1 | 1.82 -> 0.78 |
| Aria Luxe Realty | -8.4 +0.5 | -0.007 | measured | 2 | 3.65 -> 2.55 |
| Miami Tower | -5.0 -4.0 | -0.006 | estimated | 7 | 1.62 -> 1.52 |
| Maison Grande Condominium | +0.0 -0.0 | -0.095 | roof-anchored estimated | 2 | 1.82 -> 0.99 |
| Bayshore Place Condominium | -0.1 -0.1 | -0.089 | roof-anchored estimated | 2 | 9.1 -> 8.23 |
| Carbonell Brickell | -3.3 +4.2 | -0.012 | estimated | 6 | 2.16 -> 2.05 |
| MEI Condominium | +2.3 -1.3 | +0.049 | measured | 2 | 2.77 -> 1.81 |
| Faena Residences Miami | +3.9 -2.5 | -0.017 | measured | 1 | 2.82 -> 1.04 |
| Continuum on South Beach | -0.3 -2.5 | -0.052 | measured | 3 | 4.43 -> 4.14 |
| Turkey Point Nuclear Power Station (Turbine Hall) | +0.8 +6.9 | +0.002 | measured | 2 | 3.11 -> 1.29 |
| 701 Brickell Ave | +0.3 -5.6 | -0.018 | measured | 2 | 4.56 -> 2.91 |
| Brickell Arch | -2.2 -2.5 | -0.030 | measured | 8 | 3.78 -> 3.22 |
| The Palace Condominium | -0.7 +1.9 | +0.046 | estimated | 7 | 3.03 -> 2.69 |
| One Broadway | +1.3 +4.5 | -0.012 | estimated | 5 | 2.71 -> 2.46 |
| Miami-Dade County Courthouse | +4.5 +2.2 | -0.002 | estimated | 4 | 2.84 -> 2.58 |
| Loft Downtown II | -3.3 -2.6 | -0.005 | estimated | 5 | 1.06 -> 0.78 |
| Flagler on the River | +0.1 -0.1 | -0.060 | roof-anchored estimated | 9 | 5.28 -> 4.9 |
| Akoya Condominium | -0.0 -0.1 | -0.060 | roof-anchored measured | 8 | 6.05 -> 4.95 |
| Parking Garage (V16 2693) | +1.4 +4.5 | +0.000 | estimated | 1 | 2.35 -> 0.24 |
| Brickell Key One | -0.3 +0.4 | -0.051 | measured | 1 | 4.44 -> 1.74 |
| Tresor Tower | +1.7 +2.1 | -0.019 | measured | 4 | 1.39 -> 1.13 |
| Ten Museum Park | -4.1 -0.1 | +0.015 | estimated | 5 | 2.15 -> 1.81 |
| The Waverly South Beach | -0.1 +0.3 | -0.050 | roof-anchored measured | 5 | 9.93 -> 9.52 |
| 100 Biscayne Blvd | -0.1 +2.5 | -0.026 | estimated | 2 | 1.04 -> 0.52 |
| Wells Fargo Center (S) | +0.5 -0.1 | -0.044 | roof-anchored estimated | 8 | 11.91 -> 11.37 |
| Park Grove Condominium (S) | +2.7 +1.1 | -0.012 | measured | 6 | 3.96 -> 3.84 |
| Vice Beach Tower (V16 3258) | +1.6 -1.1 | -0.021 | estimated | 2 | 3.57 -> 2.58 |
| Bank of America Financial Center (Miami Beach) | -0.1 +0.4 | -0.042 | roof-anchored measured | 4 | 4.29 -> 3.96 |
| Villa del Mare | -3.6 -0.2 | -0.008 | measured | 1 | 6.25 -> 5.4 |
| Loews Miami Beach | -0.7 +2.5 | -0.011 | measured | 2 | 2.69 -> 2.25 |
| 500 Brickell | -0.9 -1.9 | +0.015 | estimated | 1 | 1.24 -> 0.05 |
| Jade Ocean Condos | -0.6 -0.7 | -0.030 | measured | 6 | 2.54 -> 2.17 |
| Murano Grande | -0.7 -3.0 | -0.002 | measured | 9 | 3.97 -> 1.48 |
| St Louis Condominium | -2.2 -0.7 | -0.008 | measured | 6 | 1.24 -> 1.12 |
| 1450 Brickell Ave | -2.6 -0.8 | +0.003 | estimated | 4 | 2.35 -> 2.3 |
| Blue Diamond | +0.3 +0.7 | -0.026 | measured | 4 | 1.33 -> 1.11 |
| Green Diamond | -1.1 -1.9 | +0.005 | measured | 3 | 3.6 -> 3.49 |
| 78 SW 13th Ave | +2.2 -1.2 | +0.000 | measured | 1 | 6.61 -> 0.04 |
| The Ritz-Carlton Bal Harbour | -0.1 -1.9 | -0.011 | measured | 5 | 5.15 -> 2.53 |
| Infinity at Brickell | -1.1 -1.2 | -0.004 | measured | 8 | 5.01 -> 4.92 |
| One Biscayne Tower | +0.1 +0.0 | +0.024 | estimated | 3 | 1.0 -> 0.28 |
| 1800 Club | +1.2 +1.2 | +0.001 | measured | 5 | 0.95 -> 0.87 |
| The Floridian | -0.0 -0.0 | -0.022 | roof-anchored measured | 4 | 1.8 -> 1.33 |
| The Crimson | +1.3 +0.4 | -0.005 | measured | 3 | 0.69 -> 0.43 |
| Marriott Miami Biscayne Bay | -1.4 -0.2 | +0.005 | estimated | 6 | 4.28 -> 2.37 |
| Met 1 Condominium | +0.1 +1.3 | +0.007 | estimated | 9 | 1.75 -> 1.46 |
| 191 NE 75th St | +1.6 -0.3 | -0.002 | measured | 1 | 5.9 -> 0.05 |
| W South Beach | +1.0 +0.5 | +0.005 | measured | 3 | 0.73 -> 0.64 |
| Wells Fargo Center | -0.2 -1.5 | +0.003 | estimated | 12 | 0.9 -> 0.73 |
| Turkey Point Nuclear Power Station (Fossil Units) | +0.0 -0.0 | -0.017 | roof-anchored measured | 3 | 1.58 -> 1.43 |
| Quantum on the Bay (South) | +1.0 -0.6 | -0.001 | measured | 12 | 3.63 -> 2.19 |
| US Sugar Mill (Factory) (North Wing) | +0.2 -0.2 | +0.013 | roof-anchored measured | 2 | 4.37 -> 4.11 |
| St. Moritz Hotel | -0.0 +0.0 | -0.015 | roof-anchored measured | 1 | 1.41 -> 1.11 |
| Isola | -0.7 +0.3 | +0.004 | measured | 1 | 0.78 -> 0.55 |
| Icon at South Beach | +0.1 +0.0 | -0.011 | roof-anchored measured | 9 | 5.63 -> 4.61 |
| Citigroup Center | -0.1 -0.0 | -0.010 | roof-anchored measured | 5 | 4.45 -> 4.2 |
| 1500 Ocean Dr | +0.0 +0.1 | -0.010 | roof-anchored measured | 1 | 2.24 -> 1.94 |
| 5959 Collins Ave | -0.0 -0.0 | -0.010 | roof-anchored measured | 3 | 1.43 -> 1.24 |
| Southeast Financial Center | -0.1 +0.1 | -0.008 | roof-anchored estimated | 26 | 1.29 -> 0.99 |
| Coast Guard Exchange | +0.3 -0.1 | +0.005 | measured | 1 | 0.53 -> 0.5 |
| Venture Apts South | +0.8 +0.1 | -0.000 | measured | 1 | 2.53 -> 0.07 |
| Vizcayne North Condominium | +0.3 +0.4 | +0.001 | estimated | 15 | 1.57 -> 1.59 |
| Marquis Miami | -0.3 +0.4 | +0.002 | measured | 9 | 4.25 -> 2.03 |
| Royal Palm South Beach | +0.0 +0.3 | -0.004 | roof-anchored measured | 4 | 4.38 -> 3.57 |
| Flamingo South Beach | -0.0 -0.0 | -0.006 | roof-anchored measured | 9 | 3.84 -> 2.8 |
| Sunset Harbour South Condo | -0.2 -0.1 | -0.004 | roof-anchored measured | 5 | 2.94 -> 2.89 |
| Brickell on the River | +0.4 -0.2 | +0.000 | measured | 1 | 3.64 -> 0.01 |
| 1111 Lincoln Rd | +0.0 -0.2 | -0.004 | roof-anchored measured | 2 | 6.31 -> 6.4 |
| Marina Blue | +0.1 -0.4 | +0.001 | roof-anchored measured | 13 | 2.92 -> 2.83 |
| US Sugar Mill (Factory) | +0.0 -0.0 | +0.005 | roof-anchored measured | 3 | 6.54 -> 6.54 |
| Turkey Point Nuclear Power Station (Containments) | +0.2 -0.2 | -0.002 | measured | 3 | 1.18 -> 0.88 |
| Opera Tower | -0.1 +0.2 | +0.002 | measured | 17 | 3.03 -> 2.59 |
| Asia Brickell Key | +0.1 +0.0 | +0.004 | roof-anchored measured | 16 | 2.74 -> 1.72 |
| Portofino Tower | +0.0 -0.2 | +0.002 | measured | 9 | 1.53 -> 1.41 |
| 50 Biscayne Blvd | -0.0 -0.0 | -0.004 | roof-anchored estimated | 6 | 1.6 -> 1.48 |
| Quantum on the Bay (North) | -0.0 -0.1 | +0.003 | roof-anchored estimated | 11 | 3.04 -> 1.57 |
| Stephen P. Clark Government Center | -0.0 +0.0 | +0.003 | roof-anchored estimated | 8 | 1.99 -> 1.96 |
| Pegassi Towers | +0.1 +0.0 | +0.003 | roof-anchored estimated | 26 | 3.17 -> 2.58 |
| Park Grove Condominium | +0.1 -0.0 | -0.002 | roof-anchored measured | 3 | 1.62 -> 1.31 |
| 1000 Venetian Way | -0.0 -0.1 | +0.002 | roof-anchored estimated | 5 | 2.93 -> 2.85 |
| One Miami Condominium West | +0.0 -0.0 | +0.003 | roof-anchored measured | 7 | 0.78 -> 0.75 |
| Apogee Condominium | +0.0 -0.1 | -0.002 | roof-anchored measured | 7 | 2.51 -> 2.42 |
| Four Seasons Hotel Miami | -0.0 -0.0 | -0.002 | roof-anchored estimated | 28 | 3.28 -> 2.82 |
| One Miami Condominium East | -0.1 +0.0 | +0.001 | roof-anchored measured | 9 | 1.21 -> 1.01 |
| Vizcayne South Condominium | -0.1 +0.1 | +0.001 | roof-anchored estimated | 8 | 2.73 -> 2.55 |
| 1045 Lincoln Rd | +0.0 +0.0 | +0.000 | measured | 0 | nan -> nan |
