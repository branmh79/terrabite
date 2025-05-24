from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from utils.geo import get_tile_grid
from utils.satellite import fetch_rgb_image
from model.inference import predict_tile
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RegionRequest(BaseModel):
    latitude: float
    longitude: float
    radius_km: float

@app.get("/")
def read_root():
    return {"message": "TerraBite API is running"}

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
        except Exception as e:
            print(f"❌ Tile error: {e}")
            score = -1

        return {
            "lat": round(tile["center_lat"], 5),
            "lon": round(tile["center_lon"], 5),
            "score": score
        }

    predictions = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_tile, tile) for tile in tiles]
        for future in as_completed(futures):
            predictions.append(future.result())

    return {"tiles": predictions}
