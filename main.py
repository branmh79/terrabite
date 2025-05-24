from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from utils.geo import get_tile_grid
from utils.satellite import fetch_rgb_image_async  # ✅ MUST be async
from model.inference import predict_tile, load_model
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import time
import torch

# Optimize CPU matmul if needed
torch.set_float32_matmul_precision('high')

# FastAPI setup
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the ML model once
MODEL = load_model()

# Request schema
class RegionRequest(BaseModel):
    latitude: float
    longitude: float
    radius_km: float

@app.get("/")
def read_root():
    return {"message": "TerraBite API is running"}

# Async processing for a single tile
async def fetch_and_score_tile(tile):
    try:
        img_array = await fetch_rgb_image_async(tile)
        if img_array is None:
            score = -1
        else:
            score = predict_tile(img_array, model=MODEL)
    except Exception as e:
        print(f"❌ Error on tile {tile}: {e}")
        score = -1

    return {
        "lat": round(tile["center_lat"], 5),
        "lon": round(tile["center_lon"], 5),
        "score": round(float(score), 3) if isinstance(score, (int, float)) else -1
    }

# Async API route that processes all tiles concurrently
@app.post("/predict")
async def predict_region(req: RegionRequest):
    start_time = time.time()
    tiles = get_tile_grid(req.latitude, req.longitude, req.radius_km)
    results = await asyncio.gather(*[fetch_and_score_tile(tile) for tile in tiles])
    print(f"✅ Processed {len(results)} tiles in {time.time() - start_time:.2f}s")
    return {"tiles": results}
