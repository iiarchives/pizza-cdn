# Copyright (c) 2024-2025 iiPython

# Modules
import os
import time
import traceback
from hashlib import md5
from pathlib import Path

from fastapi import FastAPI, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from pyvips import Image
from pyvips.error import Error

# Load domain from environment
DOMAIN = os.environ["DOMAIN"]
STATFILE = Path(os.environ.get("STATFILE", "stats.pizza"))
if not STATFILE.is_file():
    STATFILE.touch()

TTL = 3600

# Initialization
__version__ = "0.11.1"

app = FastAPI(openapi_url = None)
app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_methods = ["GET", "POST"]
)

# Handle uploads
class ImageStore:
    def __init__(self) -> None:
        self.images: dict[str, dict] = {}
        self.last_check: float = 0.0

        # Handle stats
        self.stats = {"served": 0, "served_total": int(STATFILE.read_text() or 0), "last_served": None, "recent_images": [], "version": __version__}

    def push_image(self, image_bytes: bytes) -> str:
        timestamp, image_hash = time.time(), md5(image_bytes).hexdigest()
        if image_hash not in self.images:
            print(f"[+] New image processed! MD5: {image_hash} TTL: {TTL}")

            self.images[image_hash] = {"image": image_bytes, "time": timestamp}

        # Update stats
        self.stats["served"] += 1
        self.stats["served_total"] += 1
        self.stats["last_served"] = timestamp

        if image_hash not in self.stats["recent_images"]:
            self.stats["recent_images"] = ([image_hash] + self.stats["recent_images"])[:20]

        STATFILE.write_text(str(self.stats["served_total"]))

        # Update hash access time
        self.images[image_hash]["time"] = timestamp
        return image_hash

    def fetch_image(self, image_hash: str) -> bytes | None:
        return self.images[image_hash]["image"] if image_hash in self.images else None

    def purge_old(self) -> None:
        if time.time() < self.last_check + 300:
            return

        print(f"[/] Image purge running at {round(time.time())}")
        for image_hash in list(self.images.keys()).copy():
            if time.time() - self.images[image_hash]["time"] > TTL:
                print(f"[-] {image_hash} purged due to expiration")
                del self.images[image_hash]

        self.last_check = time.time()

store = ImageStore()

# Routing
@app.get("/api/stats")
async def api_get_stats() -> JSONResponse:
    store.purge_old()
    return JSONResponse({
        "code": 200,
        "data": store.stats
    })

@app.post("/api/image")
async def upload_cover_image(file: UploadFile) -> JSONResponse:
    if not file.size:
        return JSONResponse({"code": 411, "message": "You think I'll process a file without knowing how big it is?"}, status_code = 411)

    if file.size > 100000:
        return JSONResponse({"code": 400, "message": "Image is above max size (1 megabyte)."}, status_code = 400)

    try:
        image_bytes = await file.read()

        # Load image into VIPS
        image: Image = Image.new_from_buffer(image_bytes, "")  # type: ignore

        width: int = image.width  # type: ignore
        height: int = image.height  # type: ignore
        if (width > 100 or height > 100):
            return JSONResponse({"code": 400, "message": "Image exceeds maximum dimensions (100px x 100px)."}, status_code = 400)

        # Strip out exif data
        for field in image.get_fields():
            image.remove(field)

        # Crop image to 1:1 aspect ratio
        crop_aspect = min(width, height)
        image = image.crop(
            max((width - crop_aspect) // 2, 0),
            max((height - crop_aspect) // 2, 0),
            crop_aspect,  # type: ignore
            crop_aspect
        )  # type: ignore

        # Resize to 100x100
        if image.width != 100 or image.height != 100:
            image = image.resize(100 / width, vscale = 100 / height)  # type: ignore

        # Update bytes to match our PROCESSED image
        image_bytes: bytes = image.write_to_buffer(".webp")  # type: ignore
        return JSONResponse({"code": 200, "url": f"https://{DOMAIN}/{store.push_image(image_bytes)}.webp"})

    except Error:
        return JSONResponse({"code": 400, "message": "Failed to decode client image."}, status_code = 400)

    except Exception:
        traceback.print_exc()
        return JSONResponse({"code": 500, "message": "Something went wrong, error has been logged."}, status_code = 500)

@app.get("/{file}.webp", response_model = None)
async def fetch_cover_image(file: str) -> Response | JSONResponse:
    """Fetch a specific cover by image hash."""
    image_bytes = store.fetch_image(file)
    if image_bytes is not None:
        return Response(image_bytes, media_type = "image/webp")

    return JSONResponse({"code": 404, "message": "Specified image does not exist."}, status_code = 404)

# Handle frontend
app.mount("/", StaticFiles(directory = Path(__file__).parent / "frontend", html = True))
