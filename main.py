from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from utils.satellite import generate_tiles
from model.inference import predict_tile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image
import numpy as np
import os
import time
import threading
from datetime import datetime
import uuid
import shutil
import rasterio
from fastapi import BackgroundTasks
from fastapi.responses import JSONResponse

progress = {}

# === FastAPI Setup ===
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("temp_tiles/tiles", exist_ok=True)
app.mount("/tiles", StaticFiles(directory="temp_tiles/tiles"), name="tiles")

# === Tile Prediction Request Body ===
class RegionRequest(BaseModel):
    latitude: float
    longitude: float
    radius_km: float

# === Root Endpoint ===
@app.get("/")
def read_root():
    return {"message": "TerraBite API is running"}

# === Prediction Endpoint ===
@app.post("/predict")
def predict_region(req: RegionRequest):
    # [same lat/lon calculation logic...]
    session_id = str(uuid.uuid4())
    tile_folder = os.path.join("temp_tiles", "tiles", session_id)
    os.makedirs(tile_folder, exist_ok=True)

    try:
        radius_deg = req.radius_km * 0.0088  # approximate conversion: 1 km ≈ 0.0088°
        lat_min = req.latitude - radius_deg
        lat_max = req.latitude + radius_deg
        lon_min = req.longitude - radius_deg
        lon_max = req.longitude + radius_deg
        tile_data = generate_tiles(lat_min, lon_min, lat_max, lon_max, tile_folder)
        print(f"[{session_id}] Processed {idx+1}/{len(tile_data)} tiles")
    except Exception as e:
        print(f"❌ Failed to generate tiles: {e}")
        return {"tiles": []}

    progress[session_id] = {"completed": 0, "total": len(tile_data), "stage": "prediction"}

    results = []
    for idx, tile in enumerate(tile_data):
        try:
            img = Image.open(tile["path"]).convert("RGB")
            img_array = np.array(img)
            score = predict_tile(img_array)
            tile_id = f"{session_id}/{os.path.basename(tile['path']).replace('.png', '')}"

            with rasterio.open(tile["path"]) as src:
                pixel_width_deg = abs(src.transform.a)
            tile_deg_width = pixel_width_deg * 256

            results.append({
                "lat": round(tile["lat"], 5),
                "lon": round(tile["lon"], 5),
                "score": score,
                "id": tile_id,
                "tile_width_deg": tile_deg_width
            })

            # ✅ Update progress
            progress[session_id]["completed"] += 1

        except Exception as e:
            print(f"❌ Error processing tile {tile['path']}: {e}")

    return {"tiles": results, "session_id": session_id}


@app.get("/progress/{session_id}")
def get_progress(session_id: str):
    return progress.get(session_id, {"completed": 0, "total": 0, "stage": "initializing"})

# === Background Cleanup Thread ===
FOLDER = "temp_tiles"
MAX_AGE_SECONDS = 3600  # 1 hour

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def clean_folder():
    while True:
        log("🔁 Starting cleanup cycle...")
        now = time.time()
        deleted_count = 0

        for root, _, files in os.walk(FOLDER):
            for filename in files:
                path = os.path.join(root, filename)
                if os.path.isfile(path):
                    age = now - os.path.getmtime(path)
                    if age > MAX_AGE_SECONDS:
                        try:
                            os.remove(path)
                            deleted_count += 1
                            log(f"🧹 Deleted {filename}")
                        except Exception as e:
                            log(f"❌ Error deleting {filename}: {e}")

        if deleted_count == 0:
            log("🟢 No files to delete this cycle.")
        else:
            log(f"✅ Cleanup complete. {deleted_count} file(s) removed.")

        log("😴 Sleeping for 1 hour...\n")
        time.sleep(3600)

# 🧵 Start background thread on server startup
threading.Thread(target=clean_folder, daemon=True).start()