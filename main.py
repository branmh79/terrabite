from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from utils.geo import get_tile_grid
from utils.satellite import fetch_rgb_image
from model.inference import predict_tile, load_model  # assuming load_model exists
from fastapi.middleware.cors import CORSMiddleware
from concurrent.futures import ThreadPoolExecutor
import asyncio
import time
import torch

# Set matrix precision optimization (for CPU inference if applicable)
torch.set_float32_matmul_precision('high')

# Initialize FastAPI app
app = FastAPI()

# Allow CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool reused across requests (lower overhead)
executor = ThreadPoolExecutor(max_workers=10)

# Load model once globally (adjust as needed)
MODEL = load_model()  # change this to match your setup

# Pydantic request model
class RegionRequest(BaseModel):
    latitude: float
    longitude: float
    radius_km: float

@app.get("/")
def read_root():
    return {"message": "TerraBite API is running"}

# Sync processing function (used inside async wrapper)
def sync_predict_region(req: RegionRequest):
    start_time = time.time()

    tiles = get_tile_grid(req.latitude, req.longitude, req.radius_km)

    def process_tile(tile):
        try:
            img_array = fetch_rgb_image(
                tile["lat_min"], tile["lon_min"],
                tile["lat_max"], tile["lon_max"]
            )
            score = predict_tile(img_array, model=MODEL)  # pass model explicitly
        except Exception as e:
            print(f"❌ Tile error: {e}")
            score = -1

        return {
            "lat": round(tile["center_lat"], 5),
            "lon": round(tile["center_lon"], 5),
            "score": round(float(score), 3) if isinstance(score, (int, float)) else -1
        }

    # Faster than submit/as_completed
    results = list(executor.map(process_tile, tiles))

    print(f"✅ Processed {len(results)} tiles in {time.time() - start_time:.2f}s")
    return {"tiles": results}

# Async API route that offloads work to background thread
@app.post("/predict")
async def predict_region(req: RegionRequest):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sync_predict_region, req)
