# Copyright (c) 2025 iiPython

# Modules
from pathlib import Path

from pyvips import Image
from pyvips.error import Error

# Initialization
file_store = Path(__file__).parent / "images"
if not file_store.is_dir():
    exit("pizza upgrade: images folder does not exist")

# Process images
modified = 0
for file in file_store.iterdir():
    try:
        image_bytes = file.read_bytes()

        # Load image into VIPS
        image: Image = Image.new_from_buffer(image_bytes, "")  # type: ignore

        changed = False

        # Crop image to 1:1 aspect ratio
        if image.width != image.height:
            print(f"[/] {file}: cropped to 1:1 aspect ratio")
            crop_aspect = min(image.width, image.height)
            image = image.crop(
                max((image.width - crop_aspect) // 2, 0),
                max((image.height - crop_aspect) // 2, 0),
                crop_aspect,  # type: ignore
                crop_aspect
            )  # type: ignore

            changed = True

        # Resize to 100x100
        if image.width != 100 or image.height != 100:
            image = image.resize(100 / image.width, vscale = 100 / image.height)  # type: ignore
            print(f"[/] {file}: resized to 100x100")

            changed = True

        if changed:
            file.write_bytes(image.write_to_buffer(".webp"))
            print(f"[+] {file}: modified")

            modified += 1

    except Error:
        print(f"[-] {file}: image decoding failed")

print(f"\nupgrade complete\n{modified} image(s) were modified")
