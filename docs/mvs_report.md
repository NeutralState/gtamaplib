# Global multi-view solve (MVS-V1)

Cameras (non-SOLVED) and mesh footprints/heights solved together against the pose-audit edges of all day frames and the landmark markings. Residuals in sigma units. Nothing applied unless guarded --apply.

- before: {'edge_rms_sigma': 3.974, 'edge_med_abs': 1.233, 'lm_rms_sigma': 3.145}
- after: {'edge_rms_sigma': 3.323, 'edge_med_abs': 0.917, 'lm_rms_sigma': 3.033}

## Cameras (largest changes first)

| Camera | dx dy dz (m) | dyaw dpitch droll dfov (deg) | edges | LMs | edge rms | LM rms |
|---|---|---|---|---|---|---|
| Biplane (Video) v2811 | +0.8 -6.3 +5.6 | +1.57 -2.44 +0.59 -4.27 | 8 | 4 | 8.81 -> 3.45 | 0.92 -> 1.31 |
| Speaking with Brian at Effluvia (2) | +5.3 +5.0 -2.0 | +0.45 +0.31 -0.24 -1.04 | 23 | 0 | 6.84 -> 5.03 | None -> None |
| Biplane (Video) v1080 | +7.4 +27.9 +4.6 | -1.90 -0.16 -0.42 +2.68 | 6 | 5 | 8.12 -> 2.51 | 0.43 -> 1.23 |
| Gas Station (Chase) (S) | -32.8 +3.4 +0.4 | +1.25 -0.09 -0.50 +1.91 | 6 | 5 | 7.59 -> 5.41 | 0.37 -> 0.85 |
| Speaking with Brian at Effluvia (3) | +3.5 +4.6 -1.4 | +0.17 +0.09 -0.12 -0.04 | 42 | 0 | 3.69 -> 1.92 | None -> None |
| Boat | +0.4 +27.5 +6.0 | +0.57 +0.43 +0.18 -2.74 | 7 | 1 | 4.48 -> 1.52 | 0.51 -> 0.3 |
| Amphitheater | +10.1 -33.8 -2.1 | +1.11 +0.10 -0.25 +0.08 | 7 | 6 | 6.18 -> 1.84 | 2.0 -> 1.95 |
| Biplane (Video) v1980 | -16.4 -23.7 -0.1 | -0.49 +0.06 -0.14 -1.66 | 13 | 6 | 3.81 -> 2.95 | 0.91 -> 1.17 |
| Biplane (Video) v2370 | -3.7 +22.5 +4.0 | +0.70 -0.54 +0.34 +1.38 | 1 | 7 | 1.05 -> 0.49 | 7.72 -> 6.01 |
| Oceanarium | -5.3 +19.2 +2.6 | +0.32 -0.35 -0.64 +0.67 | 35 | 0 | 4.79 -> 4.48 | None -> None |
| Street (Bikers) (B) | +1.8 +17.8 +0.1 | +0.12 -0.35 +0.59 -0.17 | 4 | 7 | 5.51 -> 0.68 | 1.11 -> 1.12 |
| House (Keys) | +0.6 -0.8 +0.0 | -0.51 -0.40 +0.04 -1.87 | 0 | 31 | None -> None | 0.81 -> 0.58 |
| Biplane (Video) v3000 | -3.9 -3.5 +0.5 | -0.52 +0.14 +0.12 -1.54 | 8 | 5 | 3.18 -> 2.55 | 1.65 -> 1.89 |
| Raul Bautista 03 (Motorboat) | -0.7 -12.8 -2.6 | +0.03 +0.29 +0.13 -0.92 | 6 | 9 | 5.86 -> 3.06 | 1.13 -> 1.63 |
| Biplane (Video) v2580 | -6.7 -6.8 -1.1 | +0.30 +0.34 +0.04 -0.94 | 31 | 10 | 6.03 -> 4.15 | 3.0 -> 3.54 |
| '95 Grotti Cheetah 04 (Garage) | +5.0 +1.9 +0.0 | -0.11 +0.02 -0.46 +0.17 | 1 | 4 | 4.5 -> 1.0 | 0.34 -> 0.5 |
| Water Tower [Gameinformer] | +0.6 +2.7 -0.0 | +0.17 -0.09 -0.36 +0.79 | 14 | 0 | 1.82 -> 1.64 | None -> None |
| Starlet Motel | -0.2 -1.9 -0.1 | -0.38 -0.10 +0.03 -1.16 | 0 | 7 | None -> None | 14.66 -> 14.36 |
| Yacht (1) | -1.5 -3.9 -0.5 | +0.16 +0.12 +0.38 +0.02 | 4 | 2 | 2.06 -> 1.69 | 0.47 -> 0.61 |
| Speaking with Brian at Effluvia (1) | -0.3 -3.8 +1.6 | +0.14 -0.21 +0.34 -0.00 | 17 | 0 | 3.01 -> 2.44 | None -> None |
| Biplane (Video) v1380 | +2.5 +3.1 -0.6 | -0.37 +0.15 -0.01 +0.75 | 15 | 6 | 1.4 -> 1.41 | 2.09 -> 1.96 |
| Character Switch in Vice Beach (A) | +0.1 -0.1 -1.7 | +0.26 -0.03 +0.28 +0.20 | 0 | 9 | None -> None | 6.78 -> 6.78 |
| Shoreline [Gameinformer] | -3.3 -8.9 +0.5 | +0.00 -0.09 -0.02 +0.31 | 29 | 0 | 1.59 -> 1.44 | None -> None |
| Street (Jason) | -1.7 -1.6 -0.1 | -0.60 -0.04 -0.06 -0.06 | 3 | 0 | 3.27 -> 0.06 | None -> None |
| Vintage Vice City Pack 02 (Port) | -5.5 +1.4 -0.0 | -0.29 +0.23 -0.09 +0.20 | 4 | 0 | 3.79 -> 1.07 | None -> None |
| Highway (Peacock Bay) (A) | +0.5 +2.8 +0.7 | -0.08 -0.06 +0.22 +0.38 | 3 | 4 | 1.93 -> 2.43 | 3.14 -> 2.87 |
| Prison (Aerial) (Biplane) | +4.0 +1.2 +1.1 | +0.16 -0.10 +0.05 -0.40 | 0 | 8 | None -> None | 3.52 -> 3.51 |
| Interchange | +0.9 +1.9 -0.2 | +0.04 +0.01 +0.20 +0.11 | 2 | 4 | 2.06 -> 0.91 | 0.61 -> 0.69 |
| Street (Lucia) (N) | +3.6 -2.4 -0.0 | +0.13 -0.23 +0.03 +0.32 | 5 | 0 | 6.07 -> 0.16 | None -> None |
| Biplane (Video) v0820 | -3.5 -2.7 +1.1 | +0.07 -0.01 -0.07 -0.13 | 21 | 12 | 3.43 -> 3.18 | 2.97 -> 3.04 |
| Grassrivers Postcard (X) | -3.1 -3.6 -0.9 | +0.00 -0.00 +0.05 +0.05 | 0 | 6 | None -> None | 4.89 -> 4.87 |
| Prison (Video) v160 | +2.1 -0.8 +0.4 | -0.14 -0.05 -0.09 -0.33 | 0 | 4 | None -> None | 0.27 -> 0.17 |
| Vice City Postcard | -0.1 -5.2 +0.2 | -0.07 -0.00 +0.03 +0.16 | 47 | 83 | 2.4 -> 1.96 | 1.83 -> 1.38 |
| Biplane Night (Video) v086 | -2.1 +1.0 -0.5 | -0.10 +0.06 -0.09 +0.31 | 0 | 5 | None -> None | 1.15 -> 1.13 |
| Parachute Jump over Vice Beach (Extended Look) | +1.5 +0.1 -1.9 | -0.08 +0.08 +0.02 +0.04 | 27 | 5 | 2.52 -> 2.29 | 0.39 -> 0.46 |
| Biplane Night (Vice Beach) | +0.5 -1.7 +0.7 | +0.11 -0.06 +0.06 -0.28 | 0 | 7 | None -> None | 0.57 -> 0.49 |
| Grassrivers 02 (Watson Bay) | +0.0 +0.3 -1.8 | -0.01 +0.03 -0.01 +0.01 | 16 | 58 | 2.93 -> 2.54 | 4.96 -> 3.13 |
| Hank's Waffle (Bocamar Bridge) | +0.3 +2.1 -0.8 | +0.21 +0.08 +0.05 +0.01 | 0 | 3 | None -> None | 0.76 -> 0.7 |
| Port Vice City (A) | -3.5 -2.4 -0.4 | -0.05 +0.02 -0.02 +0.13 | 44 | 65 | 2.64 -> 2.1 | 0.77 -> 0.74 |
| Prison (Video) v250 | +2.7 -1.5 +0.9 | +0.15 -0.04 +0.02 -0.01 | 0 | 9 | None -> None | 2.26 -> 2.35 |
| Biplane (Video) v0900 | -2.6 -2.5 +0.8 | +0.07 -0.02 -0.01 -0.06 | 16 | 13 | 2.97 -> 2.65 | 1.91 -> 1.97 |
| Vice City Sign | +1.5 -0.4 +0.0 | -0.06 +0.03 -0.10 +0.23 | 6 | 37 | 6.69 -> 5.3 | 2.31 -> 2.11 |
| Biplane Night (Video) Last | +0.4 -1.8 -0.2 | +0.10 -0.03 +0.07 -0.22 | 0 | 6 | None -> None | 2.49 -> 2.49 |
| Jason's Safehouse Vehicles (X) | +0.1 -0.1 -0.0 | +0.03 +0.07 +0.01 -0.33 | 0 | 43 | None -> None | 1.72 -> 1.48 |
| Highway (Peacock Bay) (B) | +0.5 +0.5 +0.6 | -0.01 -0.04 +0.10 -0.10 | 12 | 10 | 5.39 -> 4.44 | 1.61 -> 1.63 |
| Jet Ski | -2.7 -1.2 +0.0 | -0.10 -0.00 +0.01 -0.08 | 17 | 20 | 3.1 -> 2.78 | 0.37 -> 0.47 |
| Port Gellhorn 04 (Delights) (X) | +1.6 -0.2 -0.1 | -0.08 +0.01 -0.06 +0.03 | 0 | 4 | None -> None | 0.6 -> 0.56 |
| Prison (Video) f140 | -0.5 -0.2 +1.2 | -0.05 -0.12 -0.03 +0.02 | 0 | 8 | None -> None | 0.3 -> 0.26 |
| Grassrivers 05 (Sunrise RV Park) | -1.0 -2.9 -0.3 | +0.01 +0.01 +0.01 -0.01 | 22 | 35 | 4.28 -> 3.84 | 1.81 -> 1.81 |
| Prison (Video) f180 | +0.8 -1.4 +0.7 | -0.04 -0.05 -0.02 -0.16 | 0 | 8 | None -> None | 0.22 -> 0.2 |
| Prison (Video) v310 | +1.0 +1.3 -0.1 | +0.06 +0.00 -0.05 +0.20 | 17 | 14 | 4.43 -> 3.98 | 2.36 -> 2.37 |
| Venetian Islands | -1.6 -0.7 +0.0 | -0.01 -0.00 -0.07 -0.03 | 42 | 64 | 2.75 -> 2.59 | 1.02 -> 0.88 |
| Vice City 03 (Basketball) | +1.8 +1.4 -0.3 | +0.03 +0.03 +0.03 -0.09 | 15 | 62 | 3.58 -> 3.2 | 1.57 -> 1.09 |
| Vice City 10 (Pegassi Towers) | +1.4 -0.8 -0.5 | -0.07 +0.05 -0.01 -0.17 | 26 | 23 | 2.43 -> 1.87 | 0.87 -> 0.94 |
| Vice City 11 (Megamundo) | +1.0 +1.2 +0.3 | -0.00 -0.02 -0.05 +0.16 | 26 | 22 | 4.3 -> 3.68 | 1.47 -> 1.51 |
| Yacht (2) | -1.0 -0.6 -0.4 | +0.03 +0.04 +0.03 -0.21 | 0 | 3 | None -> None | 1.1 -> 0.01 |
| Character Switch in Vice Beach (B) | +0.6 +0.6 -0.2 | +0.04 +0.14 +0.00 +0.05 | 0 | 6 | None -> None | 2.47 -> 2.52 |
| Convertible | -0.1 -0.0 +0.0 | -0.01 +0.01 -0.08 -0.07 | 5 | 22 | 4.54 -> 3.83 | 4.24 -> 4.11 |
| Landing Gear (B) | -0.6 +0.1 -0.3 | +0.04 +0.03 -0.07 -0.09 | 0 | 5 | None -> None | 0.42 -> 0.19 |
| Motorboats (A) | +0.2 -0.0 +0.1 | +0.00 -0.01 +0.08 -0.04 | 15 | 28 | 3.64 -> 3.69 | 0.74 -> 0.75 |
| Prison (Video) f100 | -0.5 +1.7 -0.1 | +0.04 -0.01 +0.01 +0.17 | 0 | 8 | None -> None | 0.31 -> 0.3 |
| Prison (Video) v091 (Wing) | -0.5 -0.9 +0.3 | -0.05 -0.04 -0.04 -0.13 | 13 | 12 | 3.46 -> 3.49 | 4.12 -> 4.13 |
| Skyline | -0.5 -0.9 -0.2 | -0.03 +0.00 -0.04 +0.12 | 50 | 56 | 2.3 -> 2.03 | 0.55 -> 0.59 |
| VCIA Night (Runway) | -1.2 -0.4 -0.7 | -0.01 +0.01 -0.01 +0.05 | 0 | 6 | None -> None | 0.98 -> 0.97 |
| Chase (2) (A) | -0.0 -1.0 -0.0 | +0.03 +0.00 +0.00 -0.15 | 0 | 10 | None -> None | 4.54 -> 4.52 |
| Thunderstorm [Gameinformer] | +1.7 -0.7 +0.1 | -0.04 -0.06 +0.01 -0.03 | 7 | 0 | 1.75 -> 1.09 | None -> None |
| Vice Beach (A) | +1.5 -0.4 -0.4 | -0.04 +0.03 +0.03 -0.05 | 41 | 53 | 2.52 -> 2.16 | 1.59 -> 1.03 |
| Vice City 01 (Vice City Sign) | +0.1 -0.1 +0.0 | +0.02 +0.05 +0.01 +0.18 | 0 | 33 | None -> None | 1.02 -> 1.01 |
| Biplane (Video) v0770 | -0.6 -0.8 +0.2 | +0.03 -0.01 +0.01 -0.06 | 18 | 14 | 3.24 -> 3.18 | 2.86 -> 2.86 |
| Leonida Keys 05 (Boats) | +0.3 +0.4 +0.1 | -0.03 +0.02 +0.01 -0.14 | 0 | 13 | None -> None | 0.39 -> 0.37 |
| Prison | +0.7 +0.6 +0.4 | -0.01 -0.03 +0.03 +0.04 | 23 | 57 | 1.65 -> 1.17 | 3.21 -> 3.2 |
| Prison (Video) v500 | -0.0 +0.3 -0.1 | +0.01 +0.00 +0.05 +0.02 | 0 | 8 | None -> None | 0.94 -> 0.94 |
| Prison (Video) v600 | -0.1 -0.2 -0.3 | -0.01 +0.04 -0.04 +0.02 | 0 | 8 | None -> None | 1.22 -> 1.22 |
| Vice City 08 (Ferris Wheel) | -0.3 +1.2 -0.1 | -0.04 +0.03 +0.00 -0.03 | 2 | 43 | 7.43 -> 6.52 | 2.57 -> 2.51 |
| Chase (2) (B) | -0.0 -0.0 +0.0 | -0.01 -0.01 +0.03 +0.00 | 0 | 8 | None -> None | 5.5 -> 5.52 |
| Motorboats (B) | +0.1 -0.0 +0.2 | +0.01 -0.01 +0.02 -0.07 | 19 | 23 | 2.46 -> 2.45 | 0.74 -> 0.73 |
| Rooftop Party | +0.4 +0.9 +0.3 | +0.02 -0.01 +0.00 +0.04 | 31 | 33 | 4.62 -> 4.31 | 2.01 -> 2.01 |
| Shitzu Squalo 01 (Bay) | +0.5 -0.3 -0.0 | -0.03 +0.00 +0.02 +0.04 | 34 | 39 | 4.59 -> 4.44 | 0.99 -> 0.99 |
| Sunrise over Vice City (Extended Look) | -0.5 -0.2 +0.4 | +0.01 -0.02 +0.01 -0.01 | 44 | 31 | 4.34 -> 3.54 | 2.24 -> 2.22 |
| Throwing Stuff from an Overpass | +0.5 +1.0 -0.2 | -0.02 +0.01 -0.01 +0.00 | 2 | 26 | 5.5 -> 5.32 | 0.65 -> 0.65 |

## Meshes (largest changes first)

| Mesh | tx ty (m) | height scale | prior | cams | edge rms |
|---|---|---|---|---|---|
| 100 Biscayne Blvd (NE) | +7.5 +6.4 | -0.241 | estimated | 4 | 7.86 -> 6.73 |
| South Pointe Tower | -1.3 -15.8 | -0.070 | measured | 4 | 8.5 -> 5.28 |
| New Wave Condominiums | +5.2 -4.1 | -0.122 | estimated | 1 | 5.21 -> 1.02 |
| Miami Tower | -4.9 -12.8 | +0.001 | estimated | 7 | 2.18 -> 1.54 |
| The Palace Condominium | -9.7 -1.8 | +0.051 | estimated | 7 | 4.18 -> 3.88 |
| The Four Ambassadors | +3.6 +4.1 | -0.068 | measured | 1 | 4.13 -> 2.46 |
| 109 NE 2nd Ave | +1.2 +3.7 | -0.096 | measured | 2 | 4.66 -> 2.23 |
| Met 1 | +2.9 +10.2 | +0.011 | measured | 1 | 5.83 -> 0.98 |
| Carbonell Brickell | -2.2 +8.6 | -0.012 | estimated | 7 | 2.65 -> 2.07 |
| Icon Brickell | -4.7 +6.3 | -0.007 | estimated | 14 | 3.77 -> 5.11 |
| The Grand | -5.5 -3.8 | +0.021 | estimated | 12 | 2.98 -> 2.49 |
| 701 Brickell Ave | +1.6 -7.5 | -0.020 | measured | 2 | 5.27 -> 3.03 |
| Meditteranea Condo | -0.1 -0.0 | -0.106 | roof-anchored estimated | 1 | 1.82 -> 0.78 |
| MEI Condominium | +2.8 -1.2 | +0.057 | measured | 2 | 2.77 -> 1.77 |
| Maison Grande Condominium | +0.0 -0.1 | -0.095 | roof-anchored estimated | 2 | 1.82 -> 1.0 |
| Bayshore Place Condominium | -0.1 -0.1 | -0.089 | roof-anchored estimated | 2 | 9.1 -> 8.16 |
| Brickell Key One | -2.3 +0.1 | -0.063 | measured | 1 | 4.44 -> 1.54 |
| Turkey Point Nuclear Power Station (Turbine Hall) | +0.5 +8.0 | +0.002 | measured | 2 | 3.11 -> 1.14 |
| Continuum on South Beach | +0.1 -3.0 | -0.055 | measured | 3 | 4.43 -> 3.96 |
| One Broadway | +1.8 +5.2 | -0.013 | estimated | 5 | 2.83 -> 2.23 |
| Infinity at Brickell | +6.3 -2.0 | -0.000 | measured | 7 | 6.16 -> 5.46 |
| Miami-Dade County Courthouse | +4.9 +2.4 | -0.010 | estimated | 4 | 2.84 -> 2.57 |
| Brickell Arch | -1.4 -2.3 | -0.030 | measured | 8 | 3.78 -> 3.24 |
| Akoya Condominium | -0.0 -0.1 | -0.063 | roof-anchored measured | 8 | 6.05 -> 4.92 |
| Flagler on the River | +0.1 -0.2 | -0.061 | roof-anchored estimated | 8 | 5.71 -> 5.09 |
| Park Grove Condominium (S) | +3.5 +1.4 | -0.012 | measured | 6 | 3.96 -> 3.81 |
| Villa del Mare | -4.7 -0.3 | -0.010 | measured | 1 | 6.25 -> 5.26 |
| 191 NE 75th St | +2.4 -1.2 | -0.024 | measured | 1 | 7.51 -> 0.31 |
| Parking Garage (V16 2693) | +1.4 +4.5 | +0.000 | estimated | 1 | 2.35 -> 0.24 |
| Loft Downtown II | +1.2 +1.1 | -0.037 | estimated | 5 | 1.13 -> 0.75 |
| Ten Museum Park | -4.1 -0.1 | +0.015 | estimated | 5 | 2.15 -> 1.79 |
| Loews Miami Beach | -0.8 +3.2 | -0.014 | measured | 2 | 2.69 -> 2.2 |
| 100 Biscayne Blvd | -0.1 +2.6 | -0.026 | estimated | 2 | 1.04 -> 0.51 |
| Wells Fargo Center (S) | +0.6 -0.2 | -0.044 | roof-anchored estimated | 8 | 11.64 -> 11.21 |
| The Waverly South Beach | -0.1 +0.3 | -0.046 | roof-anchored measured | 5 | 9.37 -> 9.01 |
| The Bentley Bay South | -2.0 +0.6 | +0.024 | estimated | 3 | 4.93 -> 0.47 |
| 1111 Lincoln Rd | +0.0 -0.2 | -0.046 | roof-anchored measured | 2 | 4.63 -> 4.45 |
| Aria Luxe Realty | -3.8 +0.2 | -0.007 | measured | 2 | 4.38 -> 1.26 |
| St Louis Condominium | -2.7 -1.0 | -0.008 | measured | 6 | 1.49 -> 1.17 |
| Jade Ocean Condos | -0.4 -0.9 | -0.030 | measured | 6 | 2.54 -> 2.15 |
| Green Diamond | -1.3 -2.3 | +0.006 | measured | 3 | 3.6 -> 3.45 |
| Blue Diamond | +0.4 +0.7 | -0.027 | measured | 4 | 1.33 -> 1.13 |
| 78 SW 13th Ave | +2.1 -1.2 | +0.001 | measured | 1 | 6.61 -> 0.04 |
| Murano Grande | -0.3 -0.2 | +0.029 | measured | 10 | 3.7 -> 1.65 |
| 500 Brickell | -0.7 -1.4 | +0.013 | estimated | 1 | 1.23 -> 0.04 |
| The Ritz-Carlton Bal Harbour | -0.9 +1.3 | -0.005 | measured | 7 | 4.7 -> 2.41 |
| Bank of America Financial Center (Miami Beach) | +0.1 -0.6 | -0.019 | roof-anchored measured | 3 | 12.1 -> 11.72 |
| Vice Beach Tower (V16 3258) | +1.0 -0.0 | -0.016 | estimated | 2 | 1.81 -> 2.29 |
| One Biscayne Tower | -0.0 +0.0 | -0.025 | roof-anchored estimated | 3 | 3.67 -> 0.81 |
| 1800 Club | +1.2 +1.3 | -0.000 | measured | 5 | 0.96 -> 0.86 |
| Met 1 Condominium | +0.6 +1.0 | +0.006 | estimated | 9 | 1.2 -> 1.39 |
| Turkey Point Nuclear Power Station (Fossil Units) | +0.0 -0.0 | -0.021 | roof-anchored measured | 3 | 1.58 -> 1.41 |
| 1500 Ocean Dr | -0.1 +0.0 | -0.019 | roof-anchored measured | 3 | 2.26 -> 2.69 |
| St. Moritz Hotel | -0.0 +0.0 | -0.019 | roof-anchored measured | 1 | 1.41 -> 1.09 |
| Tresor Tower | -0.1 +0.9 | -0.008 | measured | 3 | 1.0 -> 0.8 |
| Marriott Miami Biscayne Bay | +0.9 +0.8 | -0.001 | estimated | 6 | 4.15 -> 2.29 |
| US Sugar Mill (Factory) (North Wing) | +0.3 -0.2 | +0.013 | roof-anchored measured | 2 | 4.37 -> 4.07 |
| The Crimson | +1.1 +0.5 | +0.001 | measured | 4 | 0.76 -> 0.49 |
| Wells Fargo Center | -0.1 -1.2 | +0.003 | estimated | 12 | 1.01 -> 0.75 |
| Isola | -0.9 +0.3 | +0.004 | measured | 1 | 0.78 -> 0.53 |
| 1450 Brickell Ave | -1.1 +0.2 | +0.003 | estimated | 4 | 2.35 -> 2.23 |
| Citigroup Center | -0.2 +0.1 | -0.013 | roof-anchored measured | 4 | 3.96 -> 3.69 |
| Apogee Condominium | +0.1 -0.1 | -0.013 | roof-anchored measured | 7 | 3.23 -> 2.39 |
| Coast Guard Exchange | +0.4 -0.1 | +0.009 | measured | 1 | 0.5 -> 1.48 |
| 5959 Collins Ave | -0.0 -0.0 | -0.011 | roof-anchored measured | 3 | 1.43 -> 1.25 |
| Marquis Miami | -0.6 +0.3 | +0.002 | measured | 9 | 4.23 -> 2.02 |
| Southeast Financial Center | -0.2 +0.1 | -0.007 | roof-anchored estimated | 25 | 1.14 -> 1.02 |
| Flamingo South Beach | -0.3 -0.2 | +0.004 | roof-anchored measured | 9 | 5.62 -> 3.78 |
| Venture Apts South | +0.8 +0.1 | -0.000 | measured | 1 | 2.53 -> 0.07 |
| Icon at South Beach | +0.0 +0.0 | -0.008 | roof-anchored measured | 9 | 5.66 -> 4.45 |
| Portofino Tower | +0.6 +0.0 | -0.002 | measured | 9 | 1.96 -> 1.46 |
| Stephen P. Clark Government Center | -0.1 +0.1 | +0.005 | roof-anchored estimated | 9 | 2.08 -> 1.86 |
| Quantum on the Bay (South) | -0.2 -0.5 | +0.000 | measured | 13 | 3.46 -> 2.04 |
| Sunset Harbour South Condo | -0.2 -0.1 | -0.004 | roof-anchored measured | 5 | 2.94 -> 2.87 |
| Marina Blue | +0.1 -0.5 | +0.001 | roof-anchored measured | 13 | 2.92 -> 2.78 |
| US Sugar Mill (Factory) | +0.0 -0.1 | +0.006 | roof-anchored measured | 3 | 6.54 -> 6.54 |
| Vizcayne North Condominium | -0.2 +0.3 | +0.002 | estimated | 15 | 1.58 -> 1.58 |
| Pegassi Towers | +0.0 -0.0 | +0.006 | roof-anchored estimated | 26 | 3.6 -> 2.62 |
| W South Beach | -0.1 +0.4 | -0.001 | roof-anchored measured | 3 | 4.65 -> 4.4 |
| Brickell on the River | +0.4 -0.2 | +0.000 | measured | 1 | 3.64 -> 0.01 |
| 50 Biscayne Blvd | +0.0 -0.0 | -0.005 | roof-anchored estimated | 6 | 1.5 -> 1.39 |
| Asia Brickell Key | +0.0 +0.0 | +0.004 | roof-anchored measured | 16 | 3.93 -> 1.82 |
| Turkey Point Nuclear Power Station (Containments) | +0.2 -0.1 | -0.002 | measured | 3 | 1.18 -> 0.87 |
| Four Seasons Hotel Miami | -0.0 +0.1 | -0.003 | roof-anchored estimated | 27 | 3.31 -> 3.02 |
| Opera Tower | -0.1 +0.2 | +0.001 | measured | 17 | 3.02 -> 2.59 |
| 1000 Venetian Way | -0.1 -0.1 | +0.002 | roof-anchored estimated | 5 | 2.93 -> 2.85 |
| Royal Palm South Beach | +0.0 +0.3 | -0.000 | roof-anchored measured | 4 | 4.63 -> 3.76 |
| One Miami Condominium West | +0.0 -0.0 | +0.003 | roof-anchored measured | 7 | 0.78 -> 0.73 |
| Park Grove Condominium | +0.2 -0.1 | -0.001 | roof-anchored measured | 3 | 1.51 -> 1.35 |
| One Miami Condominium East | -0.1 +0.0 | +0.001 | roof-anchored measured | 9 | 1.21 -> 1.0 |
| Quantum on the Bay (North) | -0.0 +0.1 | +0.002 | roof-anchored estimated | 11 | 3.23 -> 1.99 |
| Vizcayne South Condominium | -0.1 +0.1 | +0.001 | roof-anchored estimated | 8 | 2.7 -> 2.53 |
| The Floridian | -0.0 -0.1 | +0.001 | roof-anchored measured | 4 | 2.23 -> 1.47 |
| 1045 Lincoln Rd | +0.0 +0.0 | +0.000 | measured | 0 | nan -> nan |


## Applied (guarded)

Cameras applied: 7; meshes applied: 10.

### Cameras kept for review

- '95 Grotti Cheetah 04 (Garage) [4.97, 1.88, 0.03, -0.11, 0.02, -0.46, 0.17]: LM RMS 1.46' -> 2.25'
- Biplane (Video) v1080 [7.37, 27.93, 4.58, -1.9, -0.16, -0.42, 2.68]: LM RMS 2.10' -> 6.18'
- Biplane (Video) v1380 [2.54, 3.12, -0.62, -0.37, 0.15, -0.02, 0.75]: edges worse
- Biplane (Video) v1980 [-16.43, -23.68, -0.12, -0.49, 0.06, -0.14, -1.66]: LM RMS 6.25' -> 7.73'
- Biplane (Video) v2580 [-6.68, -6.83, -1.1, 0.3, 0.34, 0.04, -0.94]: LM RMS 25.97' -> 30.14'
- Biplane (Video) v2811 [0.8, -6.29, 5.62, 1.57, -2.44, 0.59, -4.27]: LM RMS 11.71' -> 16.20'
- Biplane (Video) v3000 [-3.93, -3.48, 0.46, -0.52, 0.14, 0.12, -1.54]: LM RMS 15.10' -> 16.61'
- Boat [0.42, 27.5, 5.99, 0.57, 0.43, 0.18, -2.74]: cumulative drift 28 m from its pre-MVS position (> 20 m); no landmarks and weak edge gain
- Gas Station (Chase) (S) [-32.79, 3.44, 0.43, 1.25, -0.09, -0.5, 1.91]: LM RMS 2.32' -> 5.44'
- Highway (Peacock Bay) (A) [0.5, 2.79, 0.68, -0.08, -0.06, 0.22, 0.38]: edges worse
- House (Keys) [0.61, -0.84, 0.0, -0.5, -0.4, 0.04, -1.87]: LM RMS 4.58' -> 9.90'
- Interchange [0.86, 1.94, -0.24, 0.04, 0.01, 0.2, 0.11]: LM RMS 4.42' -> 5.10'
- Oceanarium [-5.3, 19.19, 2.57, 0.32, -0.35, -0.64, 0.67]: cumulative drift 20 m from its pre-MVS position (> 20 m); no landmarks and weak edge gain
- Raul Bautista 03 (Motorboat) [-0.7, -12.79, -2.6, 0.02, 0.29, 0.13, -0.92]: LM RMS 5.68' -> 8.02'
- Shoreline [Gameinformer] [-3.26, -8.86, 0.49, 0.0, -0.09, -0.02, 0.31]: cumulative drift 47 m from its pre-MVS position (> 20 m); no landmarks and weak edge gain
- Speaking with Brian at Effluvia (1) [-0.29, -3.75, 1.57, 0.14, -0.21, 0.34, -0.0]: no landmarks and weak edge gain
- Speaking with Brian at Effluvia (2) [5.29, 4.98, -2.05, 0.45, 0.31, -0.24, -1.04]: no landmarks and weak edge gain
- Street (Bikers) (B) [1.77, 17.81, 0.07, 0.12, -0.35, 0.59, -0.17]: cumulative drift 51 m from its pre-MVS position (> 40 m)
- Street (Jason) [-1.7, -1.58, -0.06, -0.6, -0.04, -0.06, -0.06]: would go below the ground (0.5 m above the heightmap); no landmarks and weak edge gain
- Street (Lucia) (N) [3.55, -2.44, -0.0, 0.13, -0.23, 0.03, 0.32]: no landmarks and weak edge gain
- Vintage Vice City Pack 02 (Port) [-5.49, 1.4, -0.03, -0.29, 0.24, -0.09, 0.2]: street-level camera would change its eye height 1.7 -> 1.2 m; no landmarks and weak edge gain
- Water Tower [Gameinformer] [0.56, 2.7, -0.0, 0.17, -0.09, -0.36, 0.79]: no landmarks and weak edge gain
- Yacht (1) [-1.46, -3.9, -0.55, 0.16, 0.12, 0.38, 0.02]: no landmarks and weak edge gain

### Meshes kept for review

- Flagler on the River [0.113, -0.206, -0.061]: edge gain < 25 %: 5.71 -> 5.09
- Carbonell Brickell [-2.178, 8.579, -0.012]: edge gain < 25 %: 2.65 -> 2.07
- 100 Biscayne Blvd [-0.144, 2.566, -0.026]: 2 camera(s)
- 1450 Brickell Ave [-1.075, 0.204, 0.003]: edge gain < 25 %: 2.35 -> 2.23
- One Broadway [1.814, 5.223, -0.013]: edge gain < 25 %: 2.83 -> 2.23
- Wells Fargo Center (S) [0.627, -0.161, -0.044]: edge gain < 25 %: 11.64 -> 11.21
- Citigroup Center [-0.203, 0.056, -0.013]: edge gain < 25 %: 3.96 -> 3.69
- Infinity at Brickell [6.274, -2.011, -0.0]: edge gain < 25 %: 6.16 -> 5.46
- Brickell Arch [-1.399, -2.26, -0.03]: edge gain < 25 %: 3.78 -> 3.24
- Miami Tower [-4.871, -12.828, 0.001]: would cover a V16 road (0% -> 14%; roads are ground truth)
- Miami-Dade County Courthouse [4.893, 2.382, -0.01]: edge gain < 25 %: 2.84 -> 2.57
- Ten Museum Park [-4.081, -0.068, 0.015]: edge gain < 25 %: 2.15 -> 1.79
- 100 Biscayne Blvd (NE) [7.506, 6.444, -0.241]: edge gain < 25 %: 7.86 -> 6.73; change too large
- Bayshore Place Condominium [-0.101, -0.13, -0.089]: 2 camera(s); edge gain < 25 %: 9.1 -> 8.16
- Meditteranea Condo [-0.072, -0.02, -0.106]: 1 camera(s)
- Met 1 Condominium [0.623, 0.989, 0.006]: edge gain < 25 %: 1.2 -> 1.39
- The Palace Condominium [-9.69, -1.811, 0.051]: edge gain < 25 %: 4.18 -> 3.88
- New Wave Condominiums [5.176, -4.135, -0.122]: 1 camera(s)
- The Grand [-5.519, -3.756, 0.021]: edge gain < 25 %: 2.98 -> 2.49
- 1800 Club [1.242, 1.276, -0.0]: edge gain < 25 %: 0.96 -> 0.86
- US Sugar Mill (Factory) (North Wing) [0.26, -0.207, 0.013]: 2 camera(s); edge gain < 25 %: 4.37 -> 4.07
- Turkey Point Nuclear Power Station (Turbine Hall) [0.527, 7.981, 0.002]: 2 camera(s)
- Turkey Point Nuclear Power Station (Fossil Units) [0.005, -0.026, -0.021]: edge gain < 25 %: 1.58 -> 1.41
- Park Grove Condominium (S) [3.536, 1.372, -0.012]: edge gain < 25 %: 3.96 -> 3.81
- Bank of America Financial Center (Miami Beach) [0.139, -0.583, -0.019]: edge gain < 25 %: 12.1 -> 11.72
- 1500 Ocean Dr [-0.081, 0.01, -0.019]: edge gain < 25 %: 2.26 -> 2.69
- Jade Ocean Condos [-0.412, -0.943, -0.03]: edge gain < 25 %: 2.54 -> 2.15
- Maison Grande Condominium [0.028, -0.058, -0.095]: 2 camera(s)
- Blue Diamond [0.409, 0.729, -0.027]: edge gain < 25 %: 1.33 -> 1.13
- Green Diamond [-1.296, -2.281, 0.006]: edge gain < 25 %: 3.6 -> 3.45
- The Waverly South Beach [-0.137, 0.334, -0.046]: edge gain < 25 %: 9.37 -> 9.01
- Akoya Condominium [-0.032, -0.115, -0.063]: edge gain < 25 %: 6.05 -> 4.92
- Vice Beach Tower (V16 3258) [0.998, -0.012, -0.016]: 2 camera(s); edge gain < 25 %: 1.81 -> 2.29
- Parking Garage (V16 2693) [1.43, 4.52, 0.0]: 1 camera(s)
- 1111 Lincoln Rd [0.033, -0.18, -0.046]: 2 camera(s); edge gain < 25 %: 4.63 -> 4.45
- St. Moritz Hotel [-0.0, 0.009, -0.019]: 1 camera(s); edge gain < 25 %: 1.41 -> 1.09
- Loews Miami Beach [-0.763, 3.249, -0.014]: 2 camera(s); edge gain < 25 %: 2.69 -> 2.2
- MEI Condominium [2.751, -1.228, 0.057]: 2 camera(s)
- Continuum on South Beach [0.075, -3.007, -0.055]: edge gain < 25 %: 4.43 -> 3.96
- Villa del Mare [-4.728, -0.286, -0.01]: 1 camera(s); edge gain < 25 %: 6.25 -> 5.26
- Brickell Key One [-2.32, 0.145, -0.063]: 1 camera(s)
- 191 NE 75th St [2.387, -1.185, -0.024]: 1 camera(s)
- 500 Brickell [-0.669, -1.364, 0.013]: 1 camera(s)
- St Louis Condominium [-2.727, -1.049, -0.008]: edge gain < 25 %: 1.49 -> 1.17
- Icon Brickell [-4.739, 6.278, -0.007]: edge gain < 25 %: 3.77 -> 5.11
- The Four Ambassadors [3.623, 4.09, -0.068]: 1 camera(s)
- 109 NE 2nd Ave [1.181, 3.698, -0.096]: 2 camera(s)
- 701 Brickell Ave [1.55, -7.494, -0.02]: 2 camera(s)
- 78 SW 13th Ave [2.144, -1.194, 0.001]: 1 camera(s)
- 5959 Collins Ave [-0.038, -0.025, -0.011]: edge gain < 25 %: 1.43 -> 1.25
- Aria Luxe Realty [-3.821, 0.194, -0.007]: 2 camera(s)
- Met 1 [2.907, 10.25, 0.011]: 1 camera(s)
