# External data setup (bring your own files)

This repo ships **code + calibration data only**. Leak-derived binaries are
deliberately not versioned. To get the full UI working, drop these files in
place (all of them circulate in the mapping community threads):

## Required for the 3D terrain (view3d)

| File | Where to put it | What it is |
|---|---|---|
| `1.dds` (the raw 16-bit height map GPU capture, 1536x1748 L16) | `gtamapdata/heightmap/GTA6HeightMap_L16.dds` | Source of truth for all elevation. `heightmap16bit.png` (rlx) is bit-identical if you prefer to convert it back to DDS. |

Calibration: `z(m) = 706.07 * (u16 / 65535) - 301.01` — already encoded in
`gtamapdata/heightmap/heightmap_calib.json` (fitted on 73 HUD player
positions, median residual 0.18 m). Do NOT use jaxrud's original float32 tif:
it has an sRGB decode baked in (documented in the same json).

Optional HD display layer: run `python3 tools/make_terrain_hd.py` after
placing the clean full map (see below) at `~/Downloads/fullmap.png` (or edit
the path in the script). Produces `terrain_hd_f32.npy` (display only).

## Required for map backgrounds (calib Map view)

| File | Where | What |
|---|---|---|
| yanis V14 tile pyramid | `vendor/gtadb.org/maps/tiles/6/yanis,14/{z}/{z},{y},{x}.jpg` | community map tiles, zoom 0-6, 256 px, grid: 32768 m world, origin 16384, m/px = 32/2^z |
| leak clean full map (5.65 m/px) | anywhere, then run the tile script | georef: world -> px: `px = (x + 10740)/5.65`, `py = (9736 - y)/5.65`. Build the composite pyramid into `vendor/.../leak,1/` (leak over yanis, feathered edges) with the script in the session scratchpad or ask in the thread. |

## Required for camera POV overlays

Frames referenced by `cameras.json` `source` fields go under `frames/`
(gitignored). The server route `/frame/<cam>` resolves them by name.

## Not required

- `DiscordChatExporter/` — personal tooling, ignored.
- `render_camera_out/`, `renders/`, `maps/` — generated outputs.

## Quick start

```
pip install -r requirements.txt
python3 tools/server.py          # port 8765
# calib UI:  http://localhost:8765/calib.html
# 3D view:   http://localhost:8765/view3d.html
```

Everything degrades gracefully: missing height map = no terrain layer,
missing tiles = dark map background, missing frames = no POV overlay.
