# Global multi-view solve (MVS-V1)

Cameras (non-SOLVED) and mesh footprints/heights solved together against the pose-audit edges of all day frames and the landmark markings. Residuals in sigma units. Nothing applied unless guarded --apply.

- before: {'edge_rms_sigma': 4.751, 'edge_med_abs': 1.606, 'lm_rms_sigma': 3.558}
- after: {'edge_rms_sigma': 2.856, 'edge_med_abs': 0.856, 'lm_rms_sigma': 2.836}

## Cameras (largest changes first)

| Camera | dx dy dz (m) | dyaw dpitch droll dfov (deg) | edges | LMs | edge rms | LM rms |
|---|---|---|---|---|---|---|
| Motel | +0.9 +1.0 -1.7 | -2.19 +2.67 +2.30 -4.39 | 0 | 4 | None -> None | 15.02 -> 4.44 |
| Port Gellhorn 04 (Delights) (X) | -17.1 -21.7 -0.8 | -4.41 +0.84 +0.15 -1.98 | 0 | 4 | None -> None | 5.72 -> 0.97 |
| Prison (Aerial) (Biplane) | +4.1 +26.7 +17.1 | +0.68 -0.08 -1.33 +1.52 | 0 | 8 | None -> None | 14.6 -> 3.54 |
| Interchange | -9.2 -15.7 -17.5 | +0.47 +0.84 +1.48 +0.24 | 2 | 4 | 7.33 -> 1.45 | 12.01 -> 0.61 |
| Biplane (Video) v2811 | +2.7 -5.8 +4.0 | +1.61 -2.35 +0.95 -3.96 | 7 | 4 | 7.52 -> 3.59 | 0.92 -> 1.26 |
| Biplane (Video) v1080 | +6.9 +28.5 -2.1 | -1.90 +0.37 -0.89 +2.56 | 8 | 5 | 10.32 -> 2.97 | 0.43 -> 1.19 |
| Boat | -1.5 +37.1 +4.5 | +0.79 +0.64 +0.07 -3.43 | 7 | 1 | 4.18 -> 1.83 | 0.51 -> 0.13 |
| Gas Station (Chase) (S) | -33.9 +3.0 +0.3 | +1.28 -0.09 -0.49 +1.90 | 6 | 5 | 8.68 -> 5.5 | 0.37 -> 0.88 |
| Amphitheater | +12.8 -38.0 -1.4 | +1.30 +0.10 -0.14 -0.02 | 7 | 6 | 8.72 -> 1.98 | 2.0 -> 2.01 |
| Speaking with Brian at Effluvia (1) | +6.0 -3.3 +2.3 | +0.24 -0.07 +1.43 +0.75 | 19 | 0 | 8.06 -> 2.36 | None -> None |
| Biplane (Video) v3000 | -10.5 -6.7 +0.8 | -1.05 +0.49 +0.68 -2.97 | 10 | 5 | 4.42 -> 2.25 | 1.65 -> 2.01 |
| VCIA Night (Runway) | -26.6 -8.3 -12.4 | -0.03 +0.06 +0.06 +0.55 | 0 | 6 | None -> None | 3.27 -> 1.06 |
| Biplane (Video) v1380 | +9.2 +12.2 +0.9 | -1.50 -0.08 +0.09 +3.06 | 14 | 6 | 3.42 -> 1.55 | 2.41 -> 2.18 |
| Character Switch in Vice Beach (A) | -11.4 -10.0 -5.9 | +1.86 -1.26 -0.18 -0.81 | 0 | 9 | None -> None | 11.24 -> 6.71 |
| Biplane (Video) v0900 | -31.1 -15.8 +6.2 | -0.04 -0.14 +0.06 -1.10 | 20 | 13 | 3.83 -> 2.41 | 1.84 -> 2.14 |
| Shoreline [Gameinformer] | -16.1 -34.2 +1.7 | +0.39 -0.06 +0.07 +0.51 | 30 | 0 | 4.14 -> 1.99 | None -> None |
| Speaking with Brian at Effluvia (3) | +15.1 +24.2 -6.0 | +0.02 +0.41 +0.13 -0.91 | 45 | 0 | 5.25 -> 2.07 | None -> None |
| Speaking with Brian at Effluvia (2) | +7.1 +21.1 -6.5 | +0.52 +0.59 -0.08 -1.52 | 24 | 0 | 6.86 -> 4.83 | None -> None |
| Metro (SE) (B) | +0.1 -0.1 -1.0 | +0.01 +0.05 -0.03 +0.05 | 4 | 7 | 8.66 -> 9.9 | 1.69 -> 1.3 |
| Starlet Motel | -0.4 -3.6 -0.2 | -0.86 -0.23 +0.10 -2.58 | 0 | 7 | None -> None | 16.4 -> 15.46 |
| Street (Bikers) (B) | -5.1 +11.8 -5.4 | -0.72 -0.01 +0.02 +1.83 | 0 | 7 | None -> None | 1.74 -> 1.09 |
| Biplane (Video) v2370 | -2.8 +20.9 +1.2 | +0.72 -0.22 +0.08 +1.28 | 2 | 7 | 1.12 -> 0.63 | 7.72 -> 6.08 |
| Biplane (Video) v0770 | -15.7 -9.0 +5.9 | +0.27 -0.27 -0.06 -0.91 | 18 | 14 | 3.25 -> 1.02 | 2.89 -> 2.83 |
| Biplane (Video) v1980 | -10.9 -16.9 -0.3 | -0.32 +0.03 -0.15 -1.16 | 11 | 6 | 3.38 -> 3.09 | 0.91 -> 1.07 |
| Port (B) | +0.0 -0.0 +0.1 | +0.54 +0.60 +0.29 -1.69 | 5 | 2 | 1.33 -> 0.97 | 5.04 -> 2.72 |
| House (Keys) | +0.6 -0.9 -0.0 | -0.53 -0.40 +0.05 -1.95 | 0 | 31 | None -> None | 0.81 -> 0.57 |
| Prison (Video) v160 | +6.4 -3.0 +3.7 | -0.48 -0.52 -0.27 -1.24 | 0 | 4 | None -> None | 1.34 -> 0.65 |
| Raul Bautista 03 (Motorboat) | -1.4 -14.3 -2.8 | -0.04 +0.31 +0.14 -1.04 | 8 | 9 | 5.19 -> 2.83 | 1.13 -> 1.52 |
| Vintage Vice City Pack 02 (Port) | -6.1 +1.2 -7.0 | -0.27 +0.35 -0.04 +0.00 | 4 | 0 | 4.66 -> 0.44 | None -> None |
| Biplane Night (Video) Last | +0.4 -1.8 -1.2 | +0.09 -0.12 +0.62 -0.21 | 0 | 6 | None -> None | 2.83 -> 2.49 |
| Parachute Jump over Vice Beach (Extended Look) | -6.0 -4.0 -6.5 | -0.02 +0.25 +0.20 +0.28 | 27 | 5 | 2.85 -> 2.32 | 1.35 -> 0.39 |
| Prison (Video) f140 | -3.4 +3.6 +5.9 | -0.08 -0.64 -0.10 +0.52 | 0 | 8 | None -> None | 0.93 -> 0.3 |
| Chase (2) (A) | -2.2 -8.4 +1.3 | -0.15 -0.39 +0.07 -1.49 | 0 | 10 | None -> None | 7.8 -> 4.54 |
| Vice City Sign | -5.0 +6.8 -0.0 | -0.05 -0.02 -0.51 +0.51 | 6 | 0 | 6.0 -> 1.8 | None -> None |
| Oceanarium | +2.4 +2.6 +3.5 | +0.21 -0.26 -0.46 -0.07 | 31 | 0 | 4.09 -> 3.91 | None -> None |
| Chase (2) (B) | -1.5 -1.5 +0.9 | -0.84 -0.66 +0.13 -0.38 | 0 | 8 | None -> None | 9.4 -> 5.5 |
| Tennis Court (E) | -0.0 +0.0 -0.0 | +0.89 -0.17 -0.03 +0.98 | 3 | 0 | 6.26 -> 3.18 | None -> None |
| Vintage Vice City Outfits and Hairstyles 04 (Rooftop) | +0.1 -0.8 +0.3 | -0.04 +0.08 -0.53 -0.05 | 0 | 5 | None -> None | 1.93 -> 0.46 |
| Port | -0.0 +0.1 +0.4 | +0.34 -0.16 +0.21 -0.80 | 7 | 5 | 4.61 -> 2.52 | 4.38 -> 3.0 |
| Biplane (Video) v0820 | +9.3 +3.8 -3.4 | -0.08 +0.19 -0.09 +0.67 | 18 | 12 | 3.73 -> 1.26 | 2.99 -> 2.97 |
| '95 Grotti Cheetah 04 (Garage) | +5.1 +2.0 +0.1 | -0.11 +0.01 -0.44 +0.17 | 1 | 4 | 14.5 -> 1.13 | 0.34 -> 0.47 |
| Vice City 11 (Megamundo) | +7.2 +10.3 +2.2 | -0.08 -0.01 -0.06 +0.24 | 25 | 22 | 3.0 -> 1.43 | 2.43 -> 1.47 |
| Vice City 01 (Vice City Sign) | +0.5 -0.9 +0.0 | +0.17 +0.39 +0.03 +1.18 | 0 | 33 | None -> None | 1.2 -> 1.02 |
| Yacht (1) | -1.7 -3.8 -0.7 | +0.18 +0.15 +0.40 +0.10 | 4 | 2 | 2.05 -> 1.58 | 0.47 -> 0.57 |
| Biplane (Video) v2580 | -5.4 -5.9 -0.5 | +0.33 +0.21 +0.08 -0.82 | 26 | 10 | 7.27 -> 4.8 | 3.0 -> 3.46 |
| Prison (Video) v091 (Wing) | -2.3 -2.6 +1.9 | -0.21 -0.28 -0.26 -0.64 | 14 | 12 | 3.64 -> 3.58 | 4.06 -> 4.12 |
| Rooftop Party | +7.5 +8.4 +0.7 | -0.17 +0.03 -0.04 -0.35 | 29 | 33 | 5.39 -> 3.9 | 3.73 -> 2.01 |
| Sidewalk (Jason) (E) | +0.1 +0.4 -0.1 | -0.07 +0.04 -0.04 +0.06 | 18 | 19 | 5.43 -> 4.75 | 3.68 -> 3.6 |
| Sunrise over Vice City (Extended Look) | +9.8 -3.7 -1.9 | +0.02 +0.02 +0.03 +0.23 | 43 | 31 | 5.22 -> 2.33 | 2.29 -> 2.16 |
| Water Tower [Gameinformer] | +0.6 +2.7 +0.0 | +0.15 -0.10 -0.28 +0.65 | 11 | 0 | 1.7 -> 1.62 | None -> None |
| Airport (X) | -0.4 +0.1 -0.0 | -0.07 +0.03 +0.05 -0.12 | 3 | 20 | 4.95 -> 3.82 | 0.46 -> 0.46 |
| Highway (Peacock Bay) (A) | +1.4 +5.6 +0.5 | -0.16 +0.02 +0.20 +0.65 | 3 | 4 | 7.33 -> 2.82 | 3.68 -> 3.14 |
| Highway (Peacock Bay) (B) | +3.9 +6.5 +2.6 | -0.10 -0.05 +0.09 +0.01 | 11 | 10 | 8.64 -> 1.46 | 1.92 -> 1.64 |
| Ambrosia Postcard (X) | +2.5 +2.9 +3.1 | -0.06 -0.26 +0.04 -0.31 | 3 | 77 | 3.51 -> 0.9 | 7.33 -> 4.21 |
| House with Boat (X) | +0.1 +0.2 -0.1 | +0.22 -0.05 +0.12 +0.36 | 0 | 8 | None -> None | 1.42 -> 1.15 |
| Pool | -0.1 -0.0 -0.2 | +0.02 +0.22 -0.17 +0.47 | 0 | 3 | None -> None | 0.73 -> 0.36 |
| Jason Duval 05 (Machine Gun) | +4.3 -2.4 +3.0 | -0.01 -0.13 +0.04 +0.10 | 0 | 16 | None -> None | 0.77 -> 0.43 |
| Street (Jason) | -1.7 -1.6 -0.1 | -0.60 -0.04 -0.06 -0.06 | 3 | 0 | 3.27 -> 0.06 | None -> None |
| Grassrivers 05 (Sunrise RV Park) | -1.8 -2.2 -3.3 | +0.01 +0.04 +0.04 +0.00 | 29 | 35 | 4.78 -> 2.71 | 1.82 -> 1.81 |
| Grassrivers Postcard (X) | -3.4 -3.8 -0.4 | -0.03 -0.13 +0.18 +0.42 | 0 | 6 | None -> None | 5.8 -> 4.89 |
| Metro (SE) (A) (4K) | +0.1 +0.0 +0.0 | +0.37 +0.12 -0.06 -0.60 | 0 | 10 | None -> None | 1.49 -> 0.82 |
| Tennis Stadium (4K) | -0.1 +0.2 +0.1 | -0.03 -0.04 +0.03 +0.16 | 6 | 24 | 5.43 -> 2.2 | 1.99 -> 1.76 |
| Prison (Video) f180 | +2.5 -4.0 +1.3 | -0.09 -0.08 -0.04 -0.50 | 0 | 8 | None -> None | 0.35 -> 0.22 |
| Throwing Stuff from an Overpass | +0.3 -0.2 -1.6 | -0.04 +0.07 -0.22 +0.04 | 3 | 26 | 3.8 -> 3.4 | 0.67 -> 0.57 |
| Keys | +6.7 +1.1 -0.1 | -0.03 -0.09 +0.01 +0.30 | 0 | 103 | None -> None | 8.98 -> 8.95 |
| Motorboats (A) | +3.4 +0.2 -0.4 | +0.05 +0.05 +0.02 -0.61 | 17 | 28 | 4.08 -> 3.59 | 1.26 -> 0.74 |
| Tennis Court (NE) | -0.0 +0.0 +0.0 | -0.23 +0.15 +0.01 -0.52 | 1 | 4 | 1.5 -> 0.91 | 0.11 -> 0.23 |
| Car Wash | +0.0 +0.0 -0.1 | -0.13 -0.05 +0.02 +0.51 | 0 | 4 | None -> None | 0.53 -> 0.46 |
| Park | -0.1 -0.1 -0.2 | +0.03 +0.04 +0.07 -0.11 | 1 | 9 | 4.14 -> 4.03 | 0.71 -> 0.69 |
| Street (Lucia) (N) | +3.6 -2.6 -0.6 | +0.13 -0.09 +0.01 +0.30 | 5 | 0 | 6.07 -> 0.16 | None -> None |
| Tennis Court (SE) | -0.0 +0.0 -0.2 | -0.05 +0.05 +0.06 -0.10 | 0 | 6 | None -> None | 0.67 -> 0.36 |
| Biplane Night (Vice Beach) | +0.5 -1.7 +0.7 | +0.11 -0.06 +0.06 -0.28 | 0 | 7 | None -> None | 0.57 -> 0.49 |
| Grassrivers 02 (Watson Bay) | +0.0 +0.3 -1.8 | -0.01 +0.03 -0.01 +0.01 | 15 | 58 | 4.34 -> 2.77 | 4.96 -> 3.13 |
| Metro (SE) (C) | +0.0 +0.0 +0.0 | -0.12 +0.09 -0.12 +0.16 | 2 | 4 | 1.82 -> 0.21 | 0.71 -> 0.45 |
| Port Vice City (A) | -3.6 -2.2 -0.4 | -0.04 +0.02 -0.01 +0.14 | 44 | 65 | 2.9 -> 1.74 | 0.77 -> 0.74 |
| Prison (Video) v250 | +2.7 -1.5 +0.9 | +0.15 -0.04 +0.02 -0.01 | 0 | 9 | None -> None | 2.26 -> 2.35 |
| Vice City Postcard | +0.2 -3.9 +0.2 | -0.06 -0.01 +0.02 +0.11 | 51 | 83 | 4.42 -> 1.96 | 1.82 -> 1.44 |
| Diner (S) | +0.0 +0.0 +0.1 | -0.01 -0.10 -0.06 -0.04 | 0 | 4 | None -> None | 0.56 -> 0.16 |
| Ocean near Keys (N) | +0.1 -0.1 +0.0 | +0.01 +0.00 -0.01 -0.00 | 0 | 10 | None -> None | 0.23 -> 0.21 |
| Jason's Safehouse Vehicles (X) | +0.1 -0.1 -0.0 | +0.03 +0.07 +0.01 -0.34 | 0 | 43 | None -> None | 1.72 -> 1.48 |

## Meshes (largest changes first)

| Mesh | tx ty (m) | height scale | prior | cams | edge rms |
|---|---|---|---|---|---|
| Wells Fargo Center (S) | +42.8 +6.8 | -0.032 | estimated | 9 | 13.42 -> 2.58 |
| The Palace Condominium | -22.4 +6.5 | -0.133 | estimated | 8 | 5.31 -> 2.3 |
| 100 Biscayne Blvd (NE) | +7.3 +6.0 | -0.244 | estimated | 4 | 8.11 -> 6.66 |
| The Bentley Bay South | +1.2 +27.9 | -0.051 | estimated | 3 | 8.61 -> 4.34 |
| South Pointe Tower | -1.2 -15.7 | -0.156 | measured | 5 | 9.03 -> 5.27 |
| Bank of America Financial Center (Miami Beach) | -9.9 -16.4 | +0.007 | measured | 3 | 12.26 -> 3.77 |
| Miami Tower | -6.4 -15.8 | -0.037 | estimated | 8 | 2.4 -> 1.54 |
| The Floridian | -0.3 -19.1 | -0.035 | measured | 5 | 6.46 -> 1.37 |
| 1450 Brickell Ave | -11.7 -4.8 | -0.053 | estimated | 7 | 5.71 -> 4.19 |
| Met 1 Condominium | +13.7 -1.4 | -0.060 | estimated | 6 | 5.35 -> 1.96 |
| New Wave Condominiums | +4.9 -3.8 | -0.122 | estimated | 1 | 5.21 -> 1.04 |
| Murano Grande | -2.2 -9.6 | -0.081 | measured | 10 | 7.7 -> 3.58 |
| One Broadway | +7.5 -7.1 | -0.051 | estimated | 4 | 4.76 -> 2.65 |
| Miami-Dade County Courthouse | -1.3 +11.3 | -0.059 | estimated | 3 | 3.76 -> 1.85 |
| The Waverly South Beach | -1.4 +12.8 | -0.038 | measured | 4 | 8.42 -> 6.67 |
| 1000 Venetian Way | -11.2 -6.6 | -0.000 | estimated | 4 | 6.72 -> 1.16 |
| W South Beach | -4.4 +11.6 | -0.008 | measured | 3 | 4.77 -> 1.24 |
| Apogee Condominium | -13.2 +2.6 | -0.009 | measured | 7 | 7.84 -> 2.43 |
| Met 1 | +3.2 +10.7 | +0.018 | measured | 1 | 6.98 -> 1.15 |
| Portofino Tower | +5.8 +9.3 | +0.005 | measured | 9 | 1.18 -> 1.51 |
| 5959 Collins Ave | -10.8 +0.4 | -0.041 | measured | 3 | 4.24 -> 1.55 |
| Bayshore Place Condominium | -2.6 -3.1 | -0.094 | estimated | 2 | 9.1 -> 8.63 |
| 1111 Lincoln Rd | +2.0 -8.5 | -0.035 | measured | 2 | 4.63 -> 2.61 |
| 1500 Ocean Dr | -3.0 -5.7 | -0.049 | measured | 4 | 5.0 -> 2.47 |
| Citigroup Center | -8.9 +4.0 | +0.007 | measured | 3 | 6.33 -> 4.46 |
| Icon Brickell | -6.1 +7.2 | +0.002 | estimated | 16 | 4.19 -> 5.0 |
| St Louis Condominium | -10.4 +0.8 | -0.023 | measured | 5 | 2.52 -> 1.18 |
| Akoya Condominium | -2.5 -4.1 | -0.067 | measured | 8 | 6.05 -> 5.08 |
| MEI Condominium | +3.6 -3.6 | +0.060 | measured | 2 | 2.81 -> 1.3 |
| Marriott Miami Biscayne Bay | +7.1 +3.5 | +0.026 | estimated | 6 | 4.43 -> 2.02 |
| The Grand | -6.5 -4.1 | +0.022 | estimated | 12 | 3.27 -> 2.73 |
| Park Grove Condominium (S) | -0.6 +7.3 | -0.049 | measured | 6 | 3.93 -> 2.94 |
| Vizcayne South Condominium | +7.6 +5.0 | +0.002 | estimated | 10 | 3.0 -> 1.76 |
| Quantum on the Bay (North) | +5.8 -5.1 | -0.013 | estimated | 11 | 3.83 -> 2.1 |
| Vice Beach Tower (V16 3258) | +9.4 -1.3 | -0.014 | estimated | 3 | 1.08 -> 0.76 |
| Maison Grande Condominium | -0.3 -2.6 | -0.091 | estimated | 2 | 1.82 -> 0.54 |
| Infinity at Brickell | +8.1 -0.8 | -0.030 | measured | 7 | 6.93 -> 5.58 |
| Ten Museum Park | +2.8 +5.0 | -0.038 | estimated | 4 | 4.13 -> 1.58 |
| Royal Palm South Beach | +4.0 +3.5 | -0.041 | measured | 4 | 4.69 -> 2.2 |
| Park Grove Condominium | -1.1 +5.3 | -0.052 | measured | 3 | 8.15 -> 0.92 |
| The Four Ambassadors | +2.6 +3.0 | -0.058 | measured | 1 | 4.13 -> 2.14 |
| The Crimson | +4.6 +2.8 | -0.032 | measured | 4 | 1.36 -> 0.84 |
| Carbonell Brickell | -2.5 +6.6 | -0.013 | estimated | 7 | 2.66 -> 2.05 |
| Meditteranea Condo | -1.8 -0.6 | -0.079 | estimated | 1 | 1.82 -> 0.21 |
| Flagler on the River | +1.3 -2.8 | -0.058 | estimated | 7 | 6.18 -> 4.98 |
| 701 Brickell Ave | +0.7 -7.2 | -0.019 | measured | 2 | 4.36 -> 2.6 |
| 109 NE 2nd Ave | -0.5 +0.0 | -0.086 | measured | 1 | 5.17 -> 2.54 |
| Loews Miami Beach | +0.4 +1.2 | -0.074 | measured | 3 | 3.39 -> 2.07 |
| Marina Blue | +7.9 -0.6 | +0.002 | measured | 12 | 4.23 -> 2.39 |
| Stephen P. Clark Government Center | +5.3 +2.7 | -0.007 | estimated | 8 | 3.4 -> 2.09 |
| Four Seasons Hotel Miami | -4.4 +3.4 | +0.005 | estimated | 25 | 3.82 -> 2.48 |
| Turkey Point Nuclear Power Station (Turbine Hall) | +0.6 +7.4 | +0.002 | measured | 2 | 3.11 -> 1.17 |
| Brickell Key One | -4.2 +2.7 | -0.012 | measured | 4 | 6.24 -> 4.56 |
| Continuum on South Beach | -0.6 -1.4 | -0.060 | measured | 4 | 7.52 -> 3.96 |
| Asia Brickell Key | +2.1 +3.1 | -0.026 | measured | 16 | 3.99 -> 1.8 |
| Tresor Tower | +0.8 +0.5 | -0.064 | measured | 3 | 2.1 -> 1.41 |
| One Miami Condominium West | +0.9 +4.7 | -0.018 | measured | 11 | 2.65 -> 1.72 |
| Vizcayne North Condominium | +7.0 -0.2 | -0.001 | estimated | 14 | 2.38 -> 1.82 |
| 1800 Club | +2.9 +2.5 | +0.019 | measured | 5 | 1.39 -> 0.91 |
| Flamingo South Beach | +0.0 +5.7 | -0.015 | measured | 9 | 6.52 -> 1.65 |
| Pegassi Towers | -1.2 +0.1 | +0.058 | estimated | 25 | 4.73 -> 2.83 |
| Sunset Harbour South Condo | -2.3 -4.3 | -0.004 | measured | 5 | 2.93 -> 2.55 |
| Green Diamond | +1.1 -5.7 | -0.001 | measured | 3 | 5.19 -> 2.57 |
| Wells Fargo Center | -2.1 -2.0 | -0.027 | estimated | 10 | 1.84 -> 0.46 |
| Loft Downtown II | +1.8 +0.5 | -0.043 | estimated | 4 | 1.23 -> 0.83 |
| Brickell Arch | +0.3 -3.7 | -0.025 | measured | 9 | 3.71 -> 3.15 |
| US Sugar Mill (Factory) (North Wing) | +3.4 -1.5 | +0.013 | measured | 2 | 4.37 -> 3.19 |
| Tuscan Place Apartments | +4.8 +1.1 | +0.002 | measured | 2 | 14.73 -> 0.65 |
| Parking Garage (V16 2693) | +1.4 +4.5 | +0.000 | estimated | 1 | 2.35 -> 0.23 |
| 50 Biscayne Blvd | +5.6 +0.1 | +0.002 | estimated | 7 | 2.24 -> 1.51 |
| Opera Tower | +1.2 -1.8 | -0.027 | measured | 17 | 3.88 -> 2.49 |
| The Ritz-Carlton Bal Harbour | -4.9 +0.1 | -0.005 | measured | 6 | 5.52 -> 3.01 |
| 100 Biscayne Blvd | -0.1 +2.5 | -0.027 | estimated | 2 | 1.04 -> 0.53 |
| One Miami Condominium East | -4.1 -0.2 | -0.008 | measured | 8 | 2.13 -> 0.96 |
| Blue Diamond | +1.5 +3.2 | -0.002 | measured | 4 | 1.35 -> 1.18 |
| Icon at South Beach | -2.6 +1.0 | -0.007 | measured | 8 | 7.08 -> 4.58 |
| Jade Ocean Condos | -0.5 -0.4 | -0.032 | measured | 6 | 2.54 -> 2.12 |
| Turkey Point Nuclear Power Station (Fossil Units) | +0.3 -1.6 | -0.019 | measured | 3 | 1.58 -> 1.38 |
| 78 SW 13th Ave | +2.2 -1.2 | +0.000 | measured | 1 | 6.61 -> 0.04 |
| Quantum on the Bay (South) | +1.7 +1.4 | +0.002 | measured | 14 | 3.64 -> 2.17 |
| Aria Luxe Realty | -2.5 +0.1 | -0.004 | measured | 1 | 2.6 -> 1.51 |
| One Biscayne Tower | -1.4 +0.5 | -0.011 | estimated | 4 | 1.85 -> 0.3 |
| US Sugar Mill (Factory) | -0.3 -1.8 | +0.005 | measured | 3 | 6.61 -> 6.59 |
| 500 Brickell | -0.4 -0.8 | +0.014 | estimated | 1 | 0.78 -> 0.01 |
| Marquis Miami | -0.6 +0.4 | +0.009 | measured | 8 | 3.15 -> 1.78 |
| Turkey Point Nuclear Power Station (Containments) | +0.8 +0.6 | -0.003 | measured | 3 | 1.15 -> 0.78 |
| St. Moritz Hotel | -0.0 +0.3 | -0.013 | measured | 1 | 1.14 -> 0.89 |
| Southeast Financial Center | +0.1 +0.4 | -0.009 | estimated | 26 | 1.39 -> 1.0 |
| Coast Guard Exchange | +0.4 -0.1 | +0.005 | measured | 1 | 0.53 -> 0.6 |
| Venture Apts South | +0.8 +0.1 | -0.000 | measured | 1 | 2.53 -> 0.07 |
| Brickell on the River | +0.4 -0.2 | +0.000 | measured | 1 | 3.64 -> 0.01 |
| 1045 Lincoln Rd | +0.0 +0.0 | +0.000 | measured | 0 | nan -> nan |


## Applied (guarded)

Cameras applied: 43; meshes applied: 48.

### Cameras kept for review

- '95 Grotti Cheetah 04 (Garage) [5.11, 1.97, 0.12, -0.11, 0.01, -0.44, 0.17]: LM RMS 1.46' -> 2.08'
- Amphitheater [12.79, -37.95, -1.38, 1.3, 0.1, -0.14, -0.02]: move too large
- Biplane (Video) v0900 [-31.13, -15.83, 6.18, -0.04, -0.14, 0.06, -1.1]: LM RMS 17.93' -> 20.52'
- Biplane (Video) v1080 [6.93, 28.48, -2.11, -1.9, 0.37, -0.89, 2.56]: LM RMS 2.10' -> 6.02'
- Biplane (Video) v1980 [-10.92, -16.94, -0.3, -0.32, 0.03, -0.15, -1.16]: LM RMS 6.25' -> 7.17'
- Biplane (Video) v2580 [-5.44, -5.91, -0.47, 0.33, 0.21, 0.08, -0.82]: LM RMS 25.97' -> 29.49'
- Biplane (Video) v2811 [2.74, -5.77, 3.96, 1.61, -2.35, 0.95, -3.96]: LM RMS 11.71' -> 15.52'
- Biplane (Video) v3000 [-10.52, -6.69, 0.81, -1.05, 0.49, 0.68, -2.97]: LM RMS 15.10' -> 17.49'
- Boat [-1.48, 37.13, 4.48, 0.79, 0.64, 0.07, -3.43]: no landmarks and weak edge gain
- Car Wash [0.01, 0.0, -0.06, -0.13, -0.05, 0.02, 0.51]: LM RMS 4.32' -> 14.94'
- Gas Station (Chase) (S) [-33.88, 3.01, 0.3, 1.28, -0.09, -0.49, 1.9]: LM RMS 2.32' -> 5.60'
- House (Keys) [0.63, -0.88, -0.0, -0.53, -0.4, 0.05, -1.95]: LM RMS 4.58' -> 10.05'
- House with Boat (X) [0.14, 0.21, -0.06, 0.22, -0.05, 0.12, 0.36]: LM RMS 10.89' -> 15.78'
- Metro (SE) (B) [0.08, -0.08, -0.99, 0.01, 0.05, -0.03, 0.05]: edges worse
- Motel [0.88, 0.98, -1.7, -2.19, 2.67, 2.3, -4.39]: LM RMS 113.82' -> 272.89'
- Oceanarium [2.39, 2.64, 3.53, 0.21, -0.26, -0.46, -0.07]: no landmarks and weak edge gain
- Port (B) [0.01, -0.01, 0.1, 0.54, 0.6, 0.29, -1.69]: no landmarks and weak edge gain
- Raul Bautista 03 (Motorboat) [-1.41, -14.34, -2.84, -0.04, 0.31, 0.14, -1.04]: LM RMS 5.68' -> 7.47'
- Speaking with Brian at Effluvia (2) [7.05, 21.06, -6.51, 0.52, 0.59, -0.08, -1.52]: no landmarks and weak edge gain
- Street (Jason) [-1.7, -1.58, -0.06, -0.6, -0.04, -0.06, -0.06]: no landmarks and weak edge gain
- Street (Lucia) (N) [3.55, -2.56, -0.56, 0.13, -0.09, 0.01, 0.3]: no landmarks and weak edge gain
- Tennis Court (E) [-0.01, 0.0, -0.0, 0.88, -0.17, -0.03, 0.98]: no landmarks and weak edge gain
- Tennis Court (NE) [-0.01, 0.01, 0.0, -0.23, 0.15, 0.01, -0.52]: LM RMS 0.72' -> 1.41'
- Vice City Sign [-5.04, 6.78, -0.03, -0.05, -0.02, -0.51, 0.51]: no landmarks and weak edge gain
- Vintage Vice City Pack 02 (Port) [-6.06, 1.18, -7.03, -0.27, 0.36, -0.04, 0.0]: no landmarks and weak edge gain
- Water Tower [Gameinformer] [0.63, 2.68, 0.02, 0.15, -0.1, -0.28, 0.64]: no landmarks and weak edge gain
- Yacht (1) [-1.72, -3.82, -0.68, 0.18, 0.15, 0.4, 0.1]: no landmarks and weak edge gain

### Meshes kept for review

- Portofino Tower [5.768, 9.288, 0.005]: edge gain < 25 %: 1.18 -> 1.51
- Vizcayne North Condominium [6.981, -0.216, -0.001]: edge gain < 25 %: 2.38 -> 1.82
- Flagler on the River [1.274, -2.837, -0.058]: edge gain < 25 %: 6.18 -> 4.98
- Carbonell Brickell [-2.526, 6.612, -0.013]: edge gain < 25 %: 2.66 -> 2.05
- 100 Biscayne Blvd [-0.138, 2.478, -0.027]: 2 camera(s)
- Wells Fargo Center (S) [42.81, 6.839, -0.032]: change too large
- Infinity at Brickell [8.106, -0.8, -0.03]: edge gain < 25 %: 6.93 -> 5.58
- Brickell Arch [0.302, -3.693, -0.025]: edge gain < 25 %: 3.71 -> 3.15
- 100 Biscayne Blvd (NE) [7.262, 6.008, -0.244]: edge gain < 25 %: 8.11 -> 6.66; change too large
- Bayshore Place Condominium [-2.575, -3.064, -0.094]: 2 camera(s); edge gain < 25 %: 9.1 -> 8.63
- Meditteranea Condo [-1.765, -0.624, -0.079]: 1 camera(s)
- New Wave Condominiums [4.948, -3.796, -0.122]: 1 camera(s)
- The Grand [-6.527, -4.136, 0.022]: edge gain < 25 %: 3.27 -> 2.73
- US Sugar Mill (Factory) [-0.331, -1.82, 0.005]: edge gain < 25 %: 6.61 -> 6.59
- US Sugar Mill (Factory) (North Wing) [3.397, -1.468, 0.013]: 2 camera(s)
- Turkey Point Nuclear Power Station (Turbine Hall) [0.587, 7.428, 0.002]: 2 camera(s)
- Turkey Point Nuclear Power Station (Fossil Units) [0.333, -1.63, -0.019]: edge gain < 25 %: 1.58 -> 1.38
- Jade Ocean Condos [-0.476, -0.435, -0.032]: edge gain < 25 %: 2.54 -> 2.12
- Maison Grande Condominium [-0.291, -2.57, -0.091]: 2 camera(s)
- Blue Diamond [1.509, 3.16, -0.002]: edge gain < 25 %: 1.35 -> 1.18
- The Waverly South Beach [-1.419, 12.768, -0.038]: edge gain < 25 %: 8.42 -> 6.67
- Akoya Condominium [-2.544, -4.065, -0.067]: edge gain < 25 %: 6.05 -> 5.08
- The Bentley Bay South [1.162, 27.934, -0.051]: change too large
- Parking Garage (V16 2693) [1.427, 4.495, 0.0]: 1 camera(s)
- 1111 Lincoln Rd [1.981, -8.542, -0.035]: 2 camera(s)
- St. Moritz Hotel [-0.03, 0.264, -0.013]: 1 camera(s); edge gain < 25 %: 1.14 -> 0.89
- Sunset Harbour South Condo [-2.284, -4.294, -0.004]: edge gain < 25 %: 2.93 -> 2.55
- MEI Condominium [3.624, -3.642, 0.06]: 2 camera(s)
- South Pointe Tower [-1.19, -15.676, -0.156]: change too large
- Tuscan Place Apartments [4.802, 1.064, 0.002]: 2 camera(s)
- 500 Brickell [-0.372, -0.762, 0.014]: 1 camera(s)
- Icon Brickell [-6.115, 7.246, 0.002]: edge gain < 25 %: 4.19 -> 5.0
- The Four Ambassadors [2.588, 2.973, -0.058]: 1 camera(s)
- 109 NE 2nd Ave [-0.491, 0.022, -0.086]: 1 camera(s)
- 701 Brickell Ave [0.695, -7.162, -0.019]: 2 camera(s)
- 78 SW 13th Ave [2.185, -1.19, 0.0]: 1 camera(s)
- Aria Luxe Realty [-2.55, 0.141, -0.004]: 1 camera(s)
- Met 1 [3.161, 10.697, 0.018]: 1 camera(s)
