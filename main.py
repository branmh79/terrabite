from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from utils.geo import get_tile_grid
from utils.satellite import fetch_rgb_image
from model.inference import predict_tile
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from hashlib import md5
from PIL import Image
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

os.makedirs("temp_tiles", exist_ok=True)
app.mount("/tiles", StaticFiles(directory="temp_tiles"), name="tiles")

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
    tiles = get_tile_grid(req.latitude, req.longitude, req.radius_km)

    def process_tile(tile):
        try:
            img_array = fetch_rgb_image(
                tile["lat_min"], tile["lon_min"],
                tile["lat_max"], tile["lon_max"]
            )
            score = predict_tile(img_array)

            # Generate image ID from coordinates
            image_id = md5(f"{tile['center_lat']}_{tile['center_lon']}".encode()).hexdigest()
            Image.fromarray(img_array).save(f"temp_tiles/{image_id}.png")

        except Exception as e:
            print(f"❌ Tile error: {e}")
            score = -1
            image_id = "error"

        return {
            "lat": round(tile["center_lat"], 5),
            "lon": round(tile["center_lon"], 5),
            "score": score,
            "id": image_id
        }

    predictions = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_tile, tile) for tile in tiles]
        for future in as_completed(futures):
            predictions.append(future.result())

    return {"tiles": predictions}


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

        for filename in os.listdir(FOLDER):
            path = os.path.join(FOLDER, filename)
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
