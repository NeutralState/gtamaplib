from PIL import Image
import os

frames_dir = "frames"
thumbs_dir = "docs/thumbs"
os.makedirs(thumbs_dir, exist_ok=True)

# Node label -> frame filename mapping
# Key = node label (with \n replaced by space), Value = frame filename
cam_map = {
    "LK Airplane (X)": "Leonida Keys 01 (Airplane) (X)",
    "LK Postcard (X)": "Leonida Keys Postcard (X)",
    "Key Lento": "Key Lento",
    "Keys": "Keys",
    "LK 05 (Boats)": "Leonida Keys 05 (Boats)",
    "Grassrivers 02 (Watson Bay)": "Grassrivers 02 (Watson Bay)",
    "Prison": "Prison",
    "Vice Beach (A)": "Vice Beach (A)",
    "Vice Beach (B)": "Vice Beach (B)",
    "Rooftop Party": "Rooftop Party",
    "Venetian Islands": "Venetian Islands",
    "Beach": "Beach",
    "Skyline": "Skyline",
    "VC 03 (Basketball)": "Vice City 03 (Basketball)",
    "Vice City Postcard": "Vice City Postcard",
    "Motorboats (A-B)": "Motorboats (B)",
    "VC 08 (Ferris Wheel)": "Vice City 08 (Ferris Wheel)",
    "Convertible": "Convertible",
    "Raul Bautista 03 (Motorboat)": "Raul Bautista 03 (Motorboat)",
    "Peacock Bay (A)": "Highway (Peacock Bay) (A)",
    "Peacock Bay (B)": "Highway (Peacock Bay) (B)",
    "Ambrosia 02 (Panorama)": "Ambrosia 02 (Panorama)",
    "Ambrosia 04 (Fires)": "Ambrosia 04 (Fires)",
    "Chase (2) (A)": "Chase (2) (A)",
    "Chase (2) (B)": "Chase (2) (B)",
    "PGH Postcard (X)": "Port Gellhorn Postcard (X)",
    "PGH 04 (Delights) (X)": "Port Gellhorn 04 (Delights) (X)",
    "MK NP 04 (Mountain Pass) (X)": "Mount Kalaga National Park 04 (Mountain Pass) (X)",
    "Ambrosia 01 (Bikers)": "Ambrosia 01 (Bikers)",
    "Ambrosia Postcard (X)": "Ambrosia Postcard (X)",
    "Jason Duval 05 (Machine Gun)": "Jason Duval 05 (Machine Gun)",
}

done = 0
missing = []

for thumb_name, frame_name in cam_map.items():
    # Try with .png extension
    frame_path = os.path.join(frames_dir, f"{frame_name}.png")
    if not os.path.exists(frame_path):
        missing.append(frame_name)
        continue

    thumb_path = os.path.join(thumbs_dir, f"{thumb_name}.jpg")
    if os.path.exists(thumb_path):
        print(f"Skip (exists): {thumb_name}")
        continue

    img = Image.open(frame_path)
    img.thumbnail((320, 180))
    img.convert("RGB").save(thumb_path, "JPEG", quality=75)
    size = os.path.getsize(thumb_path) // 1024
    print(f"Saved: {thumb_name}.jpg ({size}KB)")
    done += 1

print(f"\nDone: {done} thumbs generated")
if missing:
    print(f"Missing frames ({len(missing)}):")
    for m in missing:
        print(f"  {m}")
