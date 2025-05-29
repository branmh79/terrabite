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

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/tiles", StaticFiles(directory="temp_tiles"), name="tiles")

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
