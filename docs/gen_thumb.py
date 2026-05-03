from PIL import Image
import os

os.makedirs("docs/thumbs", exist_ok=True)

cam_name = "Highway (Peacock Bay) (B)"
filename = f"frames/{cam_name}.png"

if os.path.exists(filename):
    img = Image.open(filename)
    img.thumbnail((320, 180))
    out = f"docs/thumbs/{cam_name}.jpg"
    img.convert("RGB").save(out, "JPEG", quality=75)
    print(f"Saved: {out} ({os.path.getsize(out)//1024}KB)")
else:
    print(f"Frame not found: {filename}")
    # List available frames
    frames = os.listdir("frames")[:10]
    print("Available:", frames)
