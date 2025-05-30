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
    delta = req.radius_km / 111
    buffered_delta = delta * 1.05  # 5% extra padding
    lat_min = req.latitude - buffered_delta
    lat_max = req.latitude + buffered_delta
    lon_min = req.longitude - buffered_delta
    lon_max = req.longitude + buffered_delta

    session_id = str(uuid.uuid4())
    tile_folder = os.path.join("temp_tiles", "tiles", session_id)
    os.makedirs(tile_folder, exist_ok=True)

    try:
        tile_data = generate_tiles(lat_min, lon_min, lat_max, lon_max, tile_folder)

    except Exception as e:
        print(f"❌ Failed to generate tiles: {e}")
        return {"tiles": []}

    results = []
    for tile in tile_data:
        try:
            img = Image.open(tile["path"]).convert("RGB")
            img_array = np.array(img)
            score = predict_tile(img_array)
            tile_id = os.path.basename(tile["path"]).replace(".png", "")

            tile_deg_width = 256 * 10 / 111000  # 256 pixels * 10m/pixel / meters per degree ≈ 0.0023 deg

            results.append({
                "lat": round(tile["lat"], 5),
                "lon": round(tile["lon"], 5),
                "score": score,
                "id": tile_id,
                "tile_width_deg": tile_deg_width
            })

        except Exception as e:
            print(f"❌ Error processing tile {tile['path']}: {e}")

    return {"tiles": results}

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
