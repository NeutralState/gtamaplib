# Global multi-view solve (MVS-V1)

Cameras (non-SOLVED) and mesh footprints/heights solved together against the pose-audit edges of all day frames and the landmark markings. Residuals in sigma units. Nothing applied unless guarded --apply.

- before: {'edge_rms_sigma': 4.041, 'edge_med_abs': 1.241, 'lm_rms_sigma': 3.041}
- after: {'edge_rms_sigma': 2.949, 'edge_med_abs': 0.895, 'lm_rms_sigma': 2.93}

## Cameras (largest changes first)

| Camera | dx dy dz (m) | dyaw dpitch droll dfov (deg) | edges | LMs | edge rms | LM rms |
|---|---|---|---|---|---|---|
| Biplane (Video) v2811 | +2.0 -5.8 +4.4 | +1.51 -2.28 +0.81 -3.85 | 7 | 4 | 7.51 -> 3.97 | 0.92 -> 1.23 |
| Biplane (Video) v1080 | +3.1 +24.2 +0.3 | -1.69 +0.17 -0.67 +2.19 | 7 | 5 | 8.02 -> 2.64 | 0.43 -> 1.17 |
| Amphitheater | +11.4 -38.2 -1.8 | +1.32 +0.21 -0.16 -0.30 | 7 | 6 | 8.91 -> 2.86 | 2.0 -> 2.03 |
| Speaking with Brian at Effluvia (2) | +15.7 +26.0 -7.4 | +0.33 +0.63 -0.01 -1.98 | 24 | 0 | 6.76 -> 4.65 | None -> None |
| Gas Station (Chase) (S) | -23.7 +5.4 +0.2 | +1.09 -0.07 -0.45 +2.65 | 5 | 5 | 8.75 -> 5.91 | 0.37 -> 1.11 |
| Boat | -0.3 +26.3 +4.7 | +0.55 +0.45 +0.16 -2.60 | 7 | 1 | 6.18 -> 1.47 | 0.51 -> 0.24 |
| Biplane (Video) v0900 | -26.4 -13.2 +4.5 | -0.03 -0.07 -0.03 -0.93 | 18 | 13 | 3.77 -> 1.88 | 1.84 -> 2.06 |
| Biplane (Video) v1980 | -14.6 -21.1 -0.1 | -0.42 +0.04 -0.15 -1.45 | 11 | 6 | 3.72 -> 3.03 | 0.91 -> 1.08 |
| Vice City Sign | -0.6 +15.8 -0.1 | -0.49 -0.15 +0.51 +0.51 | 5 | 0 | 7.29 -> 2.61 | None -> None |
| Biplane (Video) v2370 | -3.7 +13.1 +2.9 | +0.26 -0.47 +0.33 +1.09 | 1 | 7 | 0.75 -> 0.6 | 6.08 -> 5.6 |
| Oceanarium | -7.2 +6.2 +3.7 | -0.03 -0.36 -0.56 +0.40 | 35 | 0 | 4.58 -> 4.41 | None -> None |
| House (Keys) | +0.6 -0.9 -0.0 | -0.53 -0.40 +0.05 -1.94 | 0 | 31 | None -> None | 0.81 -> 0.57 |
| Biplane (Video) v1380 | +5.6 +6.4 +0.0 | -0.68 -0.14 +0.16 +1.47 | 15 | 6 | 1.84 -> 1.16 | 2.18 -> 2.12 |
| Speaking with Brian at Effluvia (3) | +5.3 +14.1 -4.4 | -0.05 +0.20 +0.10 -0.54 | 45 | 0 | 3.29 -> 2.06 | None -> None |
| Starlet Motel | -0.3 -2.5 -0.1 | -0.56 -0.14 +0.05 -1.70 | 0 | 7 | None -> None | 15.46 -> 14.97 |
| Vintage Vice City Pack 02 (Port) | -5.2 +1.1 -6.8 | -0.23 +0.34 -0.04 +0.01 | 4 | 0 | 4.38 -> 0.42 | None -> None |
| Biplane (Video) v3000 | -3.6 -3.2 +0.5 | -0.51 +0.13 +0.10 -1.47 | 8 | 5 | 3.1 -> 2.56 | 1.65 -> 1.9 |
| Shoreline [Gameinformer] | -7.2 -15.6 +0.4 | +0.07 -0.10 -0.01 +0.42 | 27 | 0 | 1.92 -> 1.93 | None -> None |
| Street (Bikers) (B) | -2.0 +12.3 -1.3 | -0.42 -0.09 -0.05 +1.06 | 2 | 7 | 14.65 -> 0.04 | 1.1 -> 0.95 |
| Biplane (Video) v2580 | -7.7 -7.8 -0.9 | +0.34 +0.34 +0.09 -1.08 | 29 | 10 | 6.38 -> 4.2 | 3.0 -> 3.65 |
| '95 Grotti Cheetah 04 (Garage) | +5.5 +1.7 +0.2 | -0.16 -0.01 -0.49 +0.26 | 1 | 4 | 4.5 -> 1.33 | 0.34 -> 0.58 |
| Raul Bautista 03 (Motorboat) | +0.0 -11.7 -2.3 | +0.08 +0.24 +0.09 -0.80 | 6 | 9 | 5.86 -> 2.97 | 1.13 -> 1.7 |
| Port Gellhorn 04 (Delights) (X) | -0.6 -2.7 -1.4 | -0.70 +0.47 -0.20 -0.08 | 0 | 4 | None -> None | 0.98 -> 0.64 |
| Yacht (1) | -2.3 -3.7 -0.7 | +0.19 +0.13 +0.39 +0.17 | 4 | 2 | 2.07 -> 1.58 | 0.47 -> 0.57 |
| Biplane (Video) v0770 | -8.0 -3.7 +3.0 | +0.08 -0.12 +0.02 -0.35 | 17 | 14 | 3.46 -> 1.37 | 2.83 -> 2.86 |
| Character Switch in Vice Beach (A) | -2.2 -1.1 -2.5 | +0.19 -0.41 +0.25 +0.22 | 0 | 9 | None -> None | 6.71 -> 6.77 |
| Prison (Video) v160 | +4.6 -1.9 +1.0 | -0.31 -0.13 -0.20 -0.76 | 0 | 4 | None -> None | 0.65 -> 0.4 |
| Street (Jason) | -1.7 -1.6 -0.1 | -0.60 -0.04 -0.06 -0.06 | 3 | 0 | 3.27 -> 0.06 | None -> None |
| VCIA Night (Runway) | -5.0 -1.8 -2.9 | -0.04 +0.06 -0.03 +0.20 | 0 | 6 | None -> None | 1.06 -> 0.98 |
| Water Tower [Gameinformer] | +0.8 +3.1 -0.0 | +0.16 -0.03 -0.13 +0.70 | 12 | 0 | 2.01 -> 1.86 | None -> None |
| Highway (Peacock Bay) (B) | +0.3 +1.3 +0.8 | -0.03 +0.01 +0.28 +0.11 | 12 | 10 | 5.82 -> 1.72 | 1.64 -> 1.6 |
| Highway (Peacock Bay) (A) | +0.8 +3.3 +0.7 | -0.09 -0.06 +0.20 +0.42 | 3 | 4 | 1.93 -> 2.14 | 3.14 -> 2.83 |
| Speaking with Brian at Effluvia (1) | +3.2 -2.2 -0.5 | -0.04 -0.15 +0.19 +0.33 | 18 | 0 | 2.99 -> 2.31 | None -> None |
| Prison (Aerial) (Biplane) | +2.8 +1.3 +1.8 | +0.15 -0.15 +0.03 -0.28 | 0 | 8 | None -> None | 3.54 -> 3.52 |
| Sunrise over Vice City (Extended Look) | +6.2 -1.3 -1.1 | -0.01 +0.01 +0.02 +0.16 | 48 | 31 | 4.77 -> 2.03 | 2.16 -> 2.18 |
| Street (Lucia) (N) | +3.5 -2.5 -0.6 | +0.13 -0.09 +0.01 +0.30 | 5 | 0 | 6.07 -> 0.16 | None -> None |
| Grassrivers Postcard (X) | -2.8 -3.3 -0.8 | +0.00 -0.00 +0.05 +0.04 | 0 | 6 | None -> None | 4.89 -> 4.87 |
| Interchange | -0.5 -1.1 -0.0 | +0.06 -0.01 +0.15 +0.20 | 2 | 4 | 2.06 -> 0.85 | 0.61 -> 0.65 |
| Parachute Jump over Vice Beach (Extended Look) | +1.0 -0.6 -1.9 | -0.08 +0.10 -0.01 +0.08 | 27 | 5 | 2.51 -> 2.29 | 0.39 -> 0.45 |
| Biplane Night (Vice Beach) | +0.5 -1.7 +0.7 | +0.11 -0.06 +0.06 -0.28 | 0 | 7 | None -> None | 0.57 -> 0.49 |
| Grassrivers 02 (Watson Bay) | +0.0 +0.3 -1.8 | -0.01 +0.03 -0.02 +0.01 | 16 | 58 | 2.8 -> 2.51 | 4.96 -> 3.13 |
| Prison (Video) v250 | +2.7 -1.5 +0.9 | +0.15 -0.04 +0.02 -0.01 | 0 | 9 | None -> None | 2.26 -> 2.35 |
| Vice City Postcard | +0.1 -4.5 +0.2 | -0.06 -0.00 +0.03 +0.12 | 48 | 83 | 2.37 -> 1.91 | 1.82 -> 1.4 |
| Port Vice City (A) | -3.3 -2.3 -0.4 | -0.05 +0.02 -0.02 +0.12 | 43 | 65 | 2.62 -> 2.12 | 0.77 -> 0.74 |
| Biplane Night (Video) Last | +0.4 -1.6 -0.2 | +0.09 -0.03 +0.07 -0.21 | 0 | 6 | None -> None | 2.49 -> 2.49 |
| Grassrivers 05 (Sunrise RV Park) | -0.8 -3.3 -0.7 | +0.02 +0.01 +0.03 +0.00 | 25 | 35 | 4.37 -> 1.54 | 1.81 -> 1.82 |
| Jason's Safehouse Vehicles (X) | +0.1 -0.1 -0.0 | +0.03 +0.07 +0.01 -0.34 | 0 | 43 | None -> None | 1.72 -> 1.48 |
| Prison (Video) f140 | -0.5 -0.2 +1.2 | -0.05 -0.12 -0.03 +0.03 | 0 | 8 | None -> None | 0.3 -> 0.26 |
| Biplane (Video) v0820 | -1.3 -1.3 +0.4 | +0.02 +0.01 -0.07 -0.04 | 20 | 12 | 3.51 -> 1.6 | 2.97 -> 3.01 |
| Jet Ski | -2.3 -0.9 +0.2 | -0.08 -0.01 +0.01 -0.05 | 18 | 20 | 3.06 -> 2.68 | 0.37 -> 0.44 |
| Motorboats (A) | +0.1 -0.0 +0.1 | +0.01 -0.01 +0.09 -0.02 | 15 | 28 | 3.64 -> 3.71 | 0.74 -> 0.75 |
| Prison (Video) f180 | +0.8 -1.4 +0.6 | -0.04 -0.05 -0.02 -0.16 | 0 | 8 | None -> None | 0.22 -> 0.2 |
| Thunderstorm [Gameinformer] | +1.8 -1.2 +0.1 | -0.08 -0.05 -0.00 +0.12 | 7 | 0 | 1.75 -> 1.08 | None -> None |
| Venetian Islands | -1.9 -0.7 +0.1 | -0.02 +0.00 -0.07 -0.04 | 43 | 64 | 2.61 -> 1.98 | 1.02 -> 0.88 |
| Vice City 03 (Basketball) | +1.9 +1.4 -0.3 | +0.03 +0.03 +0.03 -0.10 | 16 | 62 | 2.36 -> 2.45 | 1.57 -> 1.09 |
| Vice City 10 (Pegassi Towers) | +1.3 -0.7 -0.5 | -0.05 +0.05 -0.00 -0.16 | 28 | 23 | 2.61 -> 1.95 | 0.87 -> 0.91 |
| Yacht (2) | -1.0 -0.6 -0.4 | +0.03 +0.04 +0.03 -0.21 | 0 | 3 | None -> None | 1.1 -> 0.01 |
| Character Switch in Vice Beach (B) | +0.5 +0.6 -0.2 | +0.04 +0.14 -0.00 +0.05 | 0 | 6 | None -> None | 2.47 -> 2.52 |
| Convertible | -0.1 +0.0 +0.0 | -0.01 +0.01 -0.07 -0.08 | 5 | 22 | 4.54 -> 2.03 | 4.24 -> 4.11 |
| Landing Gear (B) | -0.6 +0.1 -0.3 | +0.04 +0.03 -0.06 -0.09 | 0 | 5 | None -> None | 0.42 -> 0.19 |
| Prison (Video) f100 | -0.5 +1.7 -0.1 | +0.04 -0.01 +0.01 +0.17 | 0 | 8 | None -> None | 0.31 -> 0.3 |
| Prison (Video) v091 (Wing) | -0.6 -0.9 +0.3 | -0.05 -0.04 -0.05 -0.13 | 14 | 12 | 3.31 -> 3.33 | 4.12 -> 4.13 |
| Chase (2) (A) | -0.0 -1.0 -0.0 | +0.03 +0.00 +0.00 -0.15 | 0 | 10 | None -> None | 4.54 -> 4.52 |
| Vice Beach (A) | +1.4 -0.3 -0.4 | -0.04 +0.03 +0.03 -0.04 | 39 | 53 | 2.16 -> 1.85 | 1.59 -> 1.04 |
| Vice City 01 (Vice City Sign) | +0.1 -0.1 +0.0 | +0.02 +0.05 +0.01 +0.18 | 0 | 33 | None -> None | 1.02 -> 1.01 |
| Vice City 11 (Megamundo) | +0.2 +0.1 +0.2 | +0.01 -0.02 -0.06 +0.03 | 26 | 22 | 4.16 -> 1.42 | 1.47 -> 1.48 |
| Leonida Keys 05 (Boats) | +0.3 +0.4 +0.1 | -0.03 +0.02 +0.01 -0.14 | 0 | 13 | None -> None | 0.39 -> 0.37 |
| Prison | +0.6 +0.7 +0.4 | -0.02 -0.03 +0.03 +0.03 | 25 | 57 | 1.56 -> 1.37 | 3.21 -> 3.19 |
| Prison (Video) v310 | -0.2 -1.1 +0.0 | +0.01 +0.02 +0.03 -0.06 | 17 | 14 | 4.39 -> 3.72 | 2.36 -> 2.36 |
| Prison (Video) v500 | -0.0 +0.3 -0.1 | +0.01 +0.00 +0.05 +0.02 | 0 | 8 | None -> None | 0.94 -> 0.94 |
| Prison (Video) v600 | -0.1 -0.2 -0.3 | -0.01 +0.04 -0.04 +0.01 | 0 | 8 | None -> None | 1.22 -> 1.22 |
| Rooftop Party | +0.4 +1.1 +0.3 | +0.02 -0.01 +0.01 +0.03 | 31 | 33 | 4.93 -> 3.38 | 2.01 -> 2.0 |
| Shitzu Squalo 01 (Bay) | +0.3 +0.2 +0.1 | -0.01 -0.01 +0.05 +0.01 | 35 | 39 | 4.58 -> 3.59 | 0.99 -> 0.99 |
| Skyline | -0.1 -0.5 -0.3 | -0.03 +0.01 -0.04 +0.08 | 50 | 56 | 2.3 -> 1.88 | 0.55 -> 0.57 |
| Vice City 08 (Ferris Wheel) | -0.3 +1.2 -0.1 | -0.04 +0.03 +0.00 -0.02 | 2 | 43 | 7.69 -> 6.81 | 2.57 -> 2.51 |
| Chase (2) (B) | -0.0 +0.0 +0.0 | -0.01 -0.02 +0.04 +0.02 | 0 | 8 | None -> None | 5.5 -> 5.52 |
| Motorboats (B) | -0.0 -0.0 +0.2 | +0.01 -0.01 +0.03 -0.07 | 19 | 23 | 2.25 -> 2.34 | 0.74 -> 0.74 |
| Vintage Vice City Outfits and Hairstyles 04 (Rooftop) | -0.1 -0.6 +0.1 | -0.01 -0.00 -0.03 +0.01 | 0 | 5 | None -> None | 0.46 -> 0.46 |
| AI World Editor Map (4K) | +0.1 +0.0 -0.0 | -0.01 +0.00 +0.00 -0.00 | 0 | 70 | None -> None | 0.3 -> 0.3 |
| Dominion Hotel | +0.0 -0.0 +0.0 | -0.02 -0.00 +0.00 +0.05 | 0 | 10 | None -> None | 0.22 -> 0.21 |

## Meshes (largest changes first)

| Mesh | tx ty (m) | height scale | prior | cams | edge rms |
|---|---|---|---|---|---|
| Wells Fargo Center (S) | +41.2 +6.8 | -0.034 | estimated | 8 | 11.71 -> 1.76 |
| The Waverly South Beach | -10.6 +25.2 | -0.054 | measured | 6 | 9.15 -> 5.49 |
| 100 Biscayne Blvd (NE) | +7.2 +5.8 | -0.229 | estimated | 4 | 7.85 -> 6.6 |
| The Palace Condominium | -18.7 -5.9 | +0.071 | estimated | 8 | 4.07 -> 4.14 |
| South Pointe Tower | -0.9 -17.1 | -0.134 | measured | 5 | 9.05 -> 5.54 |
| Flagler on the River | +10.4 -5.8 | -0.064 | estimated | 8 | 5.56 -> 5.24 |
| New Wave Condominiums | +5.0 -4.1 | -0.122 | estimated | 1 | 5.21 -> 1.03 |
| The Bentley Bay South | -1.9 +15.7 | -0.030 | estimated | 4 | 7.78 -> 3.51 |
| Bayshore Place Condominium | -3.2 -4.0 | -0.087 | estimated | 2 | 9.1 -> 8.2 |
| Infinity at Brickell | +4.6 -7.6 | -0.031 | measured | 8 | 6.66 -> 4.42 |
| Met 1 | +3.1 +10.3 | +0.011 | measured | 1 | 6.36 -> 1.12 |
| Akoya Condominium | -2.5 -4.4 | -0.064 | measured | 8 | 6.05 -> 4.81 |
| Maison Grande Condominium | -0.2 -3.2 | -0.093 | estimated | 2 | 1.82 -> 0.57 |
| Icon Brickell | -4.9 +6.5 | -0.003 | estimated | 15 | 3.58 -> 5.05 |
| Meditteranea Condo | -1.1 -0.5 | -0.100 | estimated | 1 | 1.82 -> 0.26 |
| 1111 Lincoln Rd | +1.6 -9.6 | +0.002 | measured | 2 | 6.31 -> 1.81 |
| Citigroup Center | -6.1 -4.2 | -0.007 | measured | 6 | 4.57 -> 4.06 |
| The Grand | -5.3 -3.6 | +0.020 | estimated | 12 | 2.99 -> 2.52 |
| Miami Tower | -5.2 -4.7 | -0.009 | estimated | 7 | 1.63 -> 1.54 |
| 1450 Brickell Ave | -6.7 -2.0 | +0.021 | estimated | 4 | 1.45 -> 0.72 |
| The Four Ambassadors | +2.2 +2.6 | -0.059 | measured | 1 | 4.13 -> 2.46 |
| Portofino Tower | +6.4 +3.7 | +0.003 | measured | 9 | 1.99 -> 1.41 |
| Marriott Miami Biscayne Bay | -6.1 -3.6 | +0.002 | estimated | 4 | 5.59 -> 1.71 |
| Capri South Beach | -4.6 +3.3 | -0.019 | measured | 1 | 6.7 -> 0.2 |
| 701 Brickell Ave | +0.6 -7.1 | -0.018 | measured | 2 | 4.82 -> 2.84 |
| MEI Condominium | +2.6 -1.4 | +0.054 | measured | 2 | 2.77 -> 1.77 |
| Vice Beach Tower (V16 3258) | +3.7 -1.9 | -0.037 | estimated | 3 | 4.74 -> 3.08 |
| 109 NE 2nd Ave | -0.4 -0.0 | -0.086 | measured | 1 | 5.31 -> 2.63 |
| Carbonell Brickell | -3.3 +4.6 | -0.011 | estimated | 6 | 2.16 -> 2.05 |
| 8 N Miami Ave | -3.9 +5.1 | +0.000 | measured | 2 | 4.59 -> 3.14 |
| Continuum on South Beach | -0.1 -1.9 | -0.068 | measured | 3 | 4.32 -> 3.4 |
| Turkey Point Nuclear Power Station (Turbine Hall) | +0.7 +7.4 | +0.002 | measured | 2 | 3.11 -> 1.2 |
| Faena Residences Miami | +4.0 -2.5 | -0.017 | measured | 1 | 2.82 -> 0.96 |
| Vizcayne North Condominium | +7.6 -0.3 | -0.003 | estimated | 14 | 2.61 -> 1.88 |
| Brickell Key One | -2.3 +0.1 | -0.056 | measured | 1 | 4.44 -> 1.58 |
| 5959 Collins Ave | -2.9 -2.6 | -0.022 | measured | 3 | 1.58 -> 1.11 |
| One Broadway | +2.5 +4.0 | -0.011 | estimated | 5 | 2.71 -> 2.05 |
| Miami-Dade County Courthouse | -2.4 +4.8 | -0.001 | estimated | 3 | 3.09 -> 2.57 |
| Sunset Harbour South Condo | -2.3 -4.4 | -0.005 | measured | 5 | 2.94 -> 2.54 |
| Brickell Arch | -1.0 -3.2 | -0.029 | measured | 9 | 3.61 -> 3.06 |
| US Sugar Mill (Factory) (North Wing) | +3.4 -1.5 | +0.013 | measured | 2 | 4.37 -> 3.18 |
| Apogee Condominium | -0.5 -5.2 | -0.003 | measured | 7 | 3.42 -> 2.26 |
| Tresor Tower | +1.8 +2.2 | -0.020 | measured | 4 | 1.39 -> 1.12 |
| Parking Garage (V16 2693) | +1.4 +4.5 | +0.000 | estimated | 1 | 2.35 -> 0.23 |
| Ten Museum Park | -4.1 -0.1 | +0.015 | estimated | 5 | 2.16 -> 1.82 |
| Bank of America Financial Center (Miami Beach) | -0.1 +0.9 | -0.047 | measured | 4 | 4.29 -> 3.89 |
| Park Grove Condominium (S) | +3.2 +1.1 | -0.012 | measured | 6 | 3.96 -> 3.82 |
| Aria Luxe Realty | -5.0 +0.3 | -0.002 | measured | 1 | 2.95 -> 2.84 |
| 100 Biscayne Blvd | -0.1 +2.6 | -0.026 | estimated | 2 | 1.04 -> 0.51 |
| Loft Downtown II | +2.8 +2.1 | -0.004 | estimated | 6 | 1.63 -> 1.33 |
| The Ritz-Carlton Bal Harbour | -2.6 -1.3 | -0.014 | measured | 6 | 5.07 -> 2.49 |
| Villa del Mare | -4.1 -0.3 | -0.009 | measured | 1 | 6.25 -> 5.36 |
| The Crimson | +2.6 +1.6 | -0.010 | measured | 3 | 0.9 -> 0.6 |
| 1500 Ocean Dr | +0.2 +3.8 | -0.011 | measured | 1 | 2.24 -> 0.99 |
| Royal Palm South Beach | +3.7 -1.1 | +0.002 | measured | 4 | 2.78 -> 1.82 |
| 1000 Venetian Way | -2.5 -1.9 | -0.006 | estimated | 4 | 2.61 -> 1.7 |
| Loews Miami Beach | -0.7 +2.9 | -0.013 | measured | 2 | 2.69 -> 2.22 |
| Jade Ocean Condos | -0.5 -0.9 | -0.030 | measured | 6 | 2.54 -> 2.15 |
| One Miami Condominium West | +2.1 +1.6 | +0.004 | measured | 7 | 1.1 -> 0.76 |
| The Floridian | +2.7 +0.6 | -0.008 | measured | 4 | 2.73 -> 2.02 |
| Green Diamond | -1.2 -2.2 | +0.006 | measured | 3 | 3.6 -> 3.48 |
| Turkey Point Nuclear Power Station (Fossil Units) | +0.4 -1.6 | -0.019 | measured | 3 | 1.58 -> 1.38 |
| St Louis Condominium | -2.3 -0.7 | -0.007 | measured | 5 | 1.14 -> 1.18 |
| Marina Blue | -0.7 -2.8 | +0.001 | measured | 13 | 2.92 -> 2.55 |
| Blue Diamond | +0.2 +0.7 | -0.026 | measured | 4 | 1.33 -> 1.1 |
| 78 SW 13th Ave | +2.2 -1.2 | +0.000 | measured | 1 | 6.61 -> 0.04 |
| Icon at South Beach | +0.8 +1.7 | -0.008 | measured | 9 | 5.59 -> 4.37 |
| 500 Brickell | -0.6 -1.2 | +0.015 | estimated | 1 | 0.91 -> 0.04 |
| Murano Grande | +1.1 -1.8 | +0.002 | measured | 10 | 4.64 -> 2.97 |
| US Sugar Mill (Factory) | -0.7 -1.8 | +0.005 | measured | 3 | 6.54 -> 6.47 |
| Asia Brickell Key | +0.2 +2.5 | -0.002 | measured | 16 | 3.99 -> 1.71 |
| One Biscayne Tower | -0.0 -0.0 | -0.026 | estimated | 3 | 4.2 -> 0.59 |
| 1800 Club | +1.2 +1.3 | +0.001 | measured | 5 | 0.95 -> 0.86 |
| Wells Fargo Center | -0.8 -1.4 | +0.003 | estimated | 10 | 0.59 -> 0.52 |
| Marquis Miami | -0.5 +0.0 | +0.018 | measured | 9 | 3.36 -> 2.17 |
| 191 NE 75th St | +1.8 -0.3 | -0.002 | measured | 1 | 14.65 -> 0.04 |
| Pegassi Towers | -0.1 -0.1 | +0.019 | estimated | 26 | 3.54 -> 2.59 |
| W South Beach | +1.1 +0.5 | +0.005 | measured | 3 | 0.73 -> 0.61 |
| Met 1 Condominium | +0.8 +0.8 | +0.005 | estimated | 9 | 1.8 -> 1.54 |
| St. Moritz Hotel | -0.0 +0.3 | -0.017 | measured | 1 | 1.41 -> 1.09 |
| Quantum on the Bay (North) | -0.4 -1.1 | +0.004 | estimated | 11 | 2.79 -> 1.79 |
| One Miami Condominium East | -1.3 -0.2 | +0.001 | measured | 9 | 1.22 -> 0.99 |
| Isola | -0.9 +0.3 | +0.004 | measured | 1 | 0.78 -> 0.57 |
| Southeast Financial Center | -0.7 -0.0 | -0.008 | estimated | 25 | 1.03 -> 0.97 |
| Quantum on the Bay (South) | +0.7 -0.7 | -0.001 | measured | 13 | 3.6 -> 2.09 |
| Stephen P. Clark Government Center | -1.2 +0.1 | +0.001 | estimated | 8 | 1.99 -> 1.95 |
| Flamingo South Beach | +0.8 -0.3 | -0.001 | measured | 10 | 5.32 -> 2.71 |
| Four Seasons Hotel Miami | -0.5 -0.5 | -0.002 | estimated | 27 | 3.19 -> 2.79 |
| Coast Guard Exchange | +0.3 -0.1 | +0.005 | measured | 1 | 0.51 -> 0.57 |
| Park Grove Condominium | +0.6 +0.2 | -0.001 | measured | 3 | 1.48 -> 1.15 |
| Venture Apts South | +0.8 +0.1 | -0.000 | measured | 1 | 2.53 -> 0.07 |
| 50 Biscayne Blvd | -0.2 -0.2 | -0.004 | estimated | 6 | 1.59 -> 1.48 |
| Vizcayne South Condominium | +0.4 +0.3 | +0.001 | estimated | 9 | 2.58 -> 2.47 |
| Turkey Point Nuclear Power Station (Containments) | +0.3 -0.2 | -0.002 | measured | 3 | 1.18 -> 0.86 |
| Brickell on the River | +0.4 -0.2 | +0.000 | measured | 1 | 3.64 -> 0.01 |
| Opera Tower | -0.1 +0.2 | +0.001 | measured | 17 | 3.03 -> 2.65 |
| 1045 Lincoln Rd | +0.0 +0.0 | +0.000 | measured | 0 | nan -> nan |


## Applied (guarded)

Cameras applied: 15; meshes applied: 22.

### Cameras kept for review

- '95 Grotti Cheetah 04 (Garage) [5.48, 1.75, 0.17, -0.16, -0.01, -0.49, 0.26]: LM RMS 1.46' -> 2.62'
- Biplane (Video) v0900 [-26.4, -13.2, 4.45, -0.03, -0.07, -0.03, -0.93]: LM RMS 17.93' -> 19.85'
- Biplane (Video) v1080 [3.06, 24.25, 0.32, -1.69, 0.17, -0.67, 2.19]: LM RMS 2.10' -> 5.84'
- Biplane (Video) v1980 [-14.6, -21.05, -0.1, -0.42, 0.04, -0.16, -1.45]: LM RMS 6.25' -> 7.21'
- Biplane (Video) v2580 [-7.74, -7.76, -0.9, 0.34, 0.34, 0.09, -1.08]: LM RMS 25.97' -> 30.97'
- Biplane (Video) v2811 [2.02, -5.77, 4.4, 1.51, -2.28, 0.81, -3.85]: LM RMS 11.71' -> 15.15'
- Biplane (Video) v3000 [-3.57, -3.2, 0.49, -0.51, 0.13, 0.1, -1.47]: LM RMS 15.10' -> 16.73'
- Boat [-0.33, 26.32, 4.73, 0.55, 0.45, 0.16, -2.6]: no landmarks and weak edge gain
- Gas Station (Chase) (S) [-23.68, 5.41, 0.23, 1.09, -0.07, -0.45, 2.65]: LM RMS 2.32' -> 7.15'
- Highway (Peacock Bay) (A) [0.78, 3.34, 0.72, -0.09, -0.06, 0.2, 0.42]: edges worse
- House (Keys) [0.63, -0.87, -0.0, -0.52, -0.4, 0.05, -1.94]: LM RMS 4.58' -> 10.05'
- Oceanarium [-7.18, 6.19, 3.73, -0.03, -0.36, -0.56, 0.4]: no landmarks and weak edge gain
- Raul Bautista 03 (Motorboat) [0.01, -11.68, -2.28, 0.08, 0.24, 0.09, -0.8]: LM RMS 5.68' -> 8.39'
- Shoreline [Gameinformer] [-7.17, -15.6, 0.43, 0.07, -0.1, -0.01, 0.42]: no landmarks and weak edge gain; edges worse
- Speaking with Brian at Effluvia (1) [3.21, -2.23, -0.46, -0.04, -0.15, 0.19, 0.33]: no landmarks and weak edge gain
- Street (Jason) [-1.7, -1.58, -0.06, -0.6, -0.04, -0.06, -0.06]: no landmarks and weak edge gain
- Street (Lucia) (N) [3.55, -2.54, -0.56, 0.13, -0.09, 0.01, 0.3]: no landmarks and weak edge gain
- Vice City Sign [-0.61, 15.79, -0.07, -0.49, -0.15, 0.51, 0.51]: no landmarks and weak edge gain
- Vintage Vice City Pack 02 (Port) [-5.23, 1.09, -6.76, -0.23, 0.34, -0.04, 0.01]: no landmarks and weak edge gain
- Water Tower [Gameinformer] [0.82, 3.09, -0.02, 0.16, -0.03, -0.13, 0.7]: no landmarks and weak edge gain
- Yacht (1) [-2.28, -3.72, -0.68, 0.19, 0.13, 0.39, 0.17]: no landmarks and weak edge gain

### Meshes kept for review

- Stephen P. Clark Government Center [-1.248, 0.059, 0.001]: edge gain < 25 %: 1.99 -> 1.95
- Marina Blue [-0.669, -2.761, 0.001]: edge gain < 25 %: 2.92 -> 2.55
- One Miami Condominium East [-1.308, -0.216, 0.001]: edge gain < 25 %: 1.22 -> 0.99
- Flagler on the River [10.431, -5.778, -0.064]: edge gain < 25 %: 5.56 -> 5.24
- Carbonell Brickell [-3.259, 4.635, -0.011]: edge gain < 25 %: 2.16 -> 2.05
- Loft Downtown II [2.846, 2.075, -0.004]: edge gain < 25 %: 1.63 -> 1.33
- 100 Biscayne Blvd [-0.131, 2.591, -0.026]: 2 camera(s)
- One Broadway [2.486, 4.044, -0.011]: edge gain < 25 %: 2.71 -> 2.05
- Wells Fargo Center [-0.787, -1.352, 0.003]: edge gain < 25 %: 0.59 -> 0.52
- Wells Fargo Center (S) [41.169, 6.816, -0.034]: change too large
- Citigroup Center [-6.077, -4.214, -0.007]: edge gain < 25 %: 4.57 -> 4.06
- Brickell Arch [-1.03, -3.181, -0.029]: edge gain < 25 %: 3.61 -> 3.06
- Miami Tower [-5.212, -4.703, -0.009]: edge gain < 25 %: 1.63 -> 1.54
- Miami-Dade County Courthouse [-2.358, 4.821, -0.001]: edge gain < 25 %: 3.09 -> 2.57
- Ten Museum Park [-4.106, -0.147, 0.015]: edge gain < 25 %: 2.16 -> 1.82
- 100 Biscayne Blvd (NE) [7.165, 5.755, -0.229]: edge gain < 25 %: 7.85 -> 6.6; change too large
- Bayshore Place Condominium [-3.162, -4.03, -0.087]: 2 camera(s); edge gain < 25 %: 9.1 -> 8.2
- Meditteranea Condo [-1.117, -0.486, -0.1]: 1 camera(s)
- Met 1 Condominium [0.83, 0.777, 0.005]: edge gain < 25 %: 1.8 -> 1.54
- The Palace Condominium [-18.704, -5.884, 0.071]: edge gain < 25 %: 4.07 -> 4.14
- New Wave Condominiums [4.99, -4.138, -0.122]: 1 camera(s)
- The Grand [-5.259, -3.562, 0.02]: edge gain < 25 %: 2.99 -> 2.52
- 1800 Club [1.169, 1.255, 0.001]: edge gain < 25 %: 0.95 -> 0.86
- US Sugar Mill (Factory) [-0.689, -1.77, 0.005]: edge gain < 25 %: 6.54 -> 6.47
- US Sugar Mill (Factory) (North Wing) [3.351, -1.465, 0.013]: 2 camera(s)
- Turkey Point Nuclear Power Station (Turbine Hall) [0.7, 7.448, 0.002]: 2 camera(s)
- Turkey Point Nuclear Power Station (Fossil Units) [0.354, -1.581, -0.019]: edge gain < 25 %: 1.58 -> 1.38
- Park Grove Condominium (S) [3.153, 1.131, -0.012]: edge gain < 25 %: 3.96 -> 3.82
- Bank of America Financial Center (Miami Beach) [-0.077, 0.862, -0.047]: edge gain < 25 %: 4.29 -> 3.89
- 1500 Ocean Dr [0.24, 3.782, -0.011]: 1 camera(s)
- Jade Ocean Condos [-0.493, -0.893, -0.03]: edge gain < 25 %: 2.54 -> 2.15
- Maison Grande Condominium [-0.184, -3.17, -0.093]: 2 camera(s)
- Blue Diamond [0.184, 0.677, -0.026]: edge gain < 25 %: 1.33 -> 1.1
- Green Diamond [-1.219, -2.19, 0.006]: edge gain < 25 %: 3.6 -> 3.48
- Icon at South Beach [0.799, 1.704, -0.008]: edge gain < 25 %: 5.59 -> 4.37
- Tresor Tower [1.773, 2.218, -0.02]: edge gain < 25 %: 1.39 -> 1.12
- The Waverly South Beach [-10.62, 25.227, -0.054]: change too large
- Akoya Condominium [-2.496, -4.392, -0.064]: edge gain < 25 %: 6.05 -> 4.81
- Parking Garage (V16 2693) [1.429, 4.497, 0.0]: 1 camera(s)
- 1111 Lincoln Rd [1.643, -9.638, 0.002]: 2 camera(s)
- Capri South Beach [-4.628, 3.267, -0.019]: 1 camera(s)
- St. Moritz Hotel [-0.04, 0.323, -0.017]: 1 camera(s); edge gain < 25 %: 1.41 -> 1.09
- Loews Miami Beach [-0.709, 2.87, -0.013]: 2 camera(s); edge gain < 25 %: 2.69 -> 2.22
- W South Beach [1.121, 0.544, 0.005]: edge gain < 25 %: 0.73 -> 0.61
- Sunset Harbour South Condo [-2.275, -4.385, -0.005]: edge gain < 25 %: 2.94 -> 2.54
- MEI Condominium [2.566, -1.374, 0.054]: 2 camera(s)
- Continuum on South Beach [-0.074, -1.938, -0.068]: edge gain < 25 %: 4.32 -> 3.4
- Villa del Mare [-4.133, -0.257, -0.009]: 1 camera(s); edge gain < 25 %: 6.25 -> 5.36
- Brickell Key One [-2.3, 0.109, -0.056]: 1 camera(s)
- 191 NE 75th St [1.793, -0.274, -0.002]: 1 camera(s)
- 500 Brickell [-0.569, -1.16, 0.015]: 1 camera(s)
- St Louis Condominium [-2.345, -0.699, -0.007]: edge gain < 25 %: 1.14 -> 1.18
- Icon Brickell [-4.926, 6.53, -0.003]: edge gain < 25 %: 3.58 -> 5.05
- The Four Ambassadors [2.217, 2.603, -0.059]: 1 camera(s)
- 109 NE 2nd Ave [-0.429, -0.039, -0.086]: 1 camera(s)
- 701 Brickell Ave [0.559, -7.116, -0.018]: 2 camera(s)
- 78 SW 13th Ave [2.183, -1.193, 0.0]: 1 camera(s)
- Faena Residences Miami [4.005, -2.504, -0.017]: 1 camera(s)
- 8 N Miami Ave [-3.852, 5.126, 0.0]: 2 camera(s)
- Aria Luxe Realty [-4.99, 0.278, -0.002]: 1 camera(s); edge gain < 25 %: 2.95 -> 2.84
- Met 1 [3.13, 10.326, 0.011]: 1 camera(s)
