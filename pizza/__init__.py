# Copyright (c) 2024-2025 iiPython

# Modules
import os
import time
import traceback
from hashlib import md5
from pathlib import Path
from datetime import datetime, time as dtime

from fastapi import FastAPI, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from pyvips import Image
from pyvips.error import Error

# Load domain from environment
DOMAIN = os.environ["DOMAIN"]

# Initialization
__version__ = "0.7.0"

app = FastAPI(openapi_url = None)
app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_methods = ["GET", "POST"]
)

file_store = Path(__file__).parents[1] / "images"
file_store.mkdir(exist_ok = True)

frontend = Path(__file__).parent / "frontend"

# Statistics
class Statistics:
    def __init__(self) -> None:

        # Handle caching
        self.last_built = 0
        self.build()

    def build(self) -> None:
        self.last_built = time.time()
        self.uploads = 0

        # Fetch todays information
        today = datetime.today().date()
        start = datetime.combine(today, dtime.min).timestamp()
        end = datetime.combine(today, dtime.max).timestamp()

        # Loop over what we already have
        sizes, times = [], []
        for file in file_store.iterdir():
            stat = file.stat()

            # Handle data
            sizes.append(stat.st_size)
            times.append((file.name, stat.st_mtime))

            if start <= stat.st_mtime <= end:
                self.uploads += 1

        sorted_times = sorted(times, key = lambda _: _[1])
        self.recent = [_[0] for _ in sorted_times[-6:]]

        self.total = len(sizes)
        self.average_size = sum(sizes) / self.total
        self.time_since_last = time.time() - sorted_times[-1][1]

        print("[+] Rebuilt statistic information!")

stats = Statistics()

# Handle frontend
@app.get("/")
async def render_index() -> FileResponse:
    return FileResponse(frontend / "index.html")

@app.get("/docs")
async def render_docs() -> FileResponse:
    return FileResponse(frontend / "docs.html")

# Routing
@app.get("/api/stats")
async def api_get_stats() -> JSONResponse:
    if time.time() > stats.last_built + 300:
        stats.build()

    return JSONResponse({
        "code": 200,
        "data": {
            "uploads": stats.uploads,
            "time_since_last": int(stats.time_since_last),
            "total": stats.total,
            "average_size": int(stats.average_size),
            "recent": stats.recent
        }
    })

@app.post("/api/image")
async def upload_cover_image(file: UploadFile) -> JSONResponse:
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

@app.get("/{file}", response_model = None)
async def fetch_cover_image(file: str) -> FileResponse | JSONResponse:
    """Fetch a specific cover by image hash."""
    file_path = file_store / file
    if not file_path.relative_to(file_store):
        return JSONResponse({"code": 401, "message": "Stop fucking with my API."}, status_code = 401)

    if not file_path.is_file():
        return JSONResponse({"code": 404, "message": "Specified file does not exist."}, status_code = 400)

    return FileResponse(file_path)
