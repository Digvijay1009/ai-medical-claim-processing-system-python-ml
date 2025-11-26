# resize_images.py
from PIL import Image
from pathlib import Path

images = Path("images")
images_out = images  # overwrite
max_width = 1200

for p in images.glob("*.png"):
    img = Image.open(p)
    w, h = img.size
    if w > max_width:
        ratio = max_width / w
        img = img.resize((int(w*ratio), int(h*ratio)), Image.LANCZOS)
        img.save(p, optimize=True)
        print("Resized", p.name)
    else:
        print("OK", p.name)
