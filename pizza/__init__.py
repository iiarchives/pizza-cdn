# Copyright (c) 2024 iiPython

# Modules
import os
import traceback
from hashlib import md5
from pathlib import Path

from fastapi import FastAPI, UploadFile
from fastapi.openapi.docs import get_redoc_html
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from pyvips import Image
from pyvips.error import Error

from apscheduler.schedulers.background import BackgroundScheduler

from .responses import generate_responses

# Load domain from environment
DOMAIN = os.environ["DOMAIN"]

# Initialization
__version__ = "0.6.2"

app = FastAPI(
    title = "iiPython's Cover Art Service",
    version = __version__,
    summary = "Public API for serving discord cover art.",
    description = "This API provides a service for you to upload 100px x 100px covers and then returns a hotlinkable URL for sending to discord (for use in RPC).",
    contact = {"name": "iiPython", "url": "https://iipython.dev", "email": "ben@iipython.dev"},
    license_info = {"name": "MIT", "url": "https://opensource.org/license/MIT"},
    docs_url = None,
    redoc_url = None
)
app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_methods = ["GET", "POST"]
)

file_store = Path(__file__).parents[1] / "images"
file_store.mkdir(exist_ok = True)

# Handle docs
@app.get("/docs", include_in_schema = False)
async def render_redoc() -> HTMLResponse:
    return get_redoc_html(
        openapi_url = "/openapi.json",
        title = "iiPython's Cover Art Service",
        redoc_favicon_url = ""
    )

# Handle generating stitch
def generate_stitch() -> None:
    image_list = sorted(file_store.iterdir())
    if not image_list:
        return

    tiles = []
    for image in image_list:
        if image.name == "stitch.webp":
            continue

        tile = Image.new_from_file(image, access = "sequential")
        if tile.bands == 3:  # type: ignore
            tile = tile.bandjoin(255)  # type: ignore

        tiles.append(tile.colourspace("srgb"))  # type: ignore

    image = Image.arrayjoin(tiles, across = 20)  # type: ignore
    image.write_to_file(file_store / "stitch.webp")

generate_stitch()

scheduler = BackgroundScheduler()
scheduler.add_job(generate_stitch, "interval", hours = 12)
scheduler.start()

# Routing
@app.get("/", name = "Index")
async def render_index() -> FileResponse:
    """Basic HTML page showing the latest stitch of all covers, regenerated every 12 hours."""
    return FileResponse(Path(__file__).parent / "index.html")

@app.post("/api/image", responses = generate_responses([200, 201, 400, 411, 500]))
async def upload_cover_image(file: UploadFile) -> JSONResponse:
    """Upload an image and generate a public URL for it. Exif data will be removed on the server side."""
    if not file.size:
        return JSONResponse({"code": 411, "message": "You think I'll save a file without knowing how big it is?"}, status_code = 411)

    if file.size > 100000:
        return JSONResponse({"code": 400, "message": "Image is above max size (1 megabyte)."}, status_code = 400)

    try:
        image_bytes = await file.read()

        # Load image into VIPS
        image: Image = Image.new_from_buffer(image_bytes, "")  # type: ignore
        if (image.width > 100 or image.height > 100):  # type: ignore
            return JSONResponse({"code": 400, "message": "Image exceeds maximum dimensions (100px x 100px)."}, status_code = 400)

        # Process hash for storage
        file_path = (file_store / (md5(image_bytes).hexdigest())).with_suffix(".webp")
        if not file_path.is_file():

            # Strip out exif data
            for field in image.get_fields():
                image.remove(field)

            image.write_to_file(file_path)
            return JSONResponse({"code": 201, "url": f"https://{DOMAIN}/{file_path.name}"}, status_code = 201)

        return JSONResponse({"code": 200, "url": f"https://{DOMAIN}/{file_path.name}"})

    except Error:
        return JSONResponse({"code": 400, "message": "Failed to decode client image."}, status_code = 400)

    except Exception:
        traceback.print_exc()
        return JSONResponse({"code": 500, "message": "Something went wrong, error has been logged."}, status_code = 500)

@app.get("/{file}", response_model = None, responses = {})
async def fetch_cover_image(file: str) -> FileResponse | JSONResponse:
    """Fetch a specific cover by image hash."""
    file_path = file_store / file
    if not file_path.relative_to(file_store):
        return JSONResponse({"code": 401, "message": "Stop fucking with my API."}, status_code = 401)

    if not file_path.is_file():
        return JSONResponse({"code": 404, "message": "Specified file does not exist."}, status_code = 400)

    return FileResponse(file_path)
