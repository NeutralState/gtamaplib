#!/bin/zsh
# Suite du pipeline V16 v3 une fois les 32 pieces rendues: tuiles z0-z6, raster 1 m/px + crops maps.json.
set -e
cd /Users/alexandreleblanc/Downloads/gtamaplib-main
P=maps/v16_z6_v3
n=$(ls $P | grep -c '^c[01]_r[0-9][0-9]\.png$')
if [ "$n" -ne 32 ]; then echo "pieces incompletes: $n/32"; exit 1; fi
echo "== tuiles z0-z6"; /usr/local/bin/python3 tools/v16/build_tiles_from_pieces.py $P 16991 11008 vendor/gtadb.org/maps/tiles/6/yanis,16 0 6
echo "== raster + crops"; cp maps/yanis,16svg.png maps/yanis,16svg_v20260912.png; /usr/local/bin/python3 tools/v16/raster_from_pieces.py $P maps/yanis,16svg.png 16991 11008 --crops
echo "== FIN"
