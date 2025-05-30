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
    # Convert center + radius to bounding box
    delta = req.radius_km / 111  # ~km to degrees
    lat_min = req.latitude - delta
    lat_max = req.latitude + delta
    lon_min = req.longitude - delta
    lon_max = req.longitude + delta

    try:
        tile_paths = generate_tiles(lat_min, lon_min, lat_max, lon_max)
    except Exception as e:
        print(f"❌ Failed to generate tiles: {e}")
        return {"tiles": []}

    results = []
    for path in tile_paths:
        try:
            img_array = np.array(Image.open(path))
            score = predict_tile(img_array)
            filename = os.path.basename(path).replace(".png", "")
            results.append({
                "lat": round((lat_min + lat_max) / 2, 5),  # or use tile center logic later
                "lon": round((lon_min + lon_max) / 2, 5),
                "score": score,
                "id": filename
            })
        except Exception as e:
            print(f"❌ Error processing tile {path}: {e}")

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
