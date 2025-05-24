from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from utils.geo import get_tile_grid
from utils.satellite import fetch_rgb_image_async
from model.inference import predict_tile_batch, load_model
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import time
import torch

# Optimize CPU matmul if needed
torch.set_float32_matmul_precision('high')

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL = load_model()

class RegionRequest(BaseModel):
    latitude: float
    longitude: float
    radius_km: float

@app.get("/")
def read_root():
    return {"message": "TerraBite API is running"}

# Semaphore to limit concurrent downloads
semaphore = asyncio.Semaphore(5)

async def fetch_single_tile(tile):
    async with semaphore:
        img_array = await fetch_rgb_image_async(tile)
        return tile, img_array

@app.post("/predict")
async def predict_region(req: RegionRequest):
    start_time = time.time()
    tiles = get_tile_grid(req.latitude, req.longitude, req.radius_km)

    # Download all tile images concurrently with limit
    tile_image_pairs = await asyncio.gather(*[fetch_single_tile(tile) for tile in tiles])

    # Filter out failed downloads
    valid_pairs = [(tile, img) for tile, img in tile_image_pairs if img is not None]
    tile_data, image_arrays = zip(*valid_pairs) if valid_pairs else ([], [])

    # Batched inference
    scores = predict_tile_batch(image_arrays, model=MODEL)

    results = []
    for tile, score in zip(tile_data, scores):
        results.append({
            "lat": round(tile["center_lat"], 5),
            "lon": round(tile["center_lon"], 5),
            "score": round(score, 3)
        })

    print(f"✅ Processed {len(results)} tiles in {time.time() - start_time:.2f}s")
    return {"tiles": results}
