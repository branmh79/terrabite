from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "TerraBite API is running"}

# Request schema
class RegionRequest(BaseModel):
    latitude: float
    longitude: float
    radius_km: float

# Response schema (optional, but useful)
class TilePrediction(BaseModel):
    lat: float
    lon: float
    score: float

@app.post("/predict")
def predict_region(req: RegionRequest) -> dict:
    # Dummy response for testing
    predictions = [
        {"lat": req.latitude + 0.01, "lon": req.longitude + 0.01, "score": 0.72},
        {"lat": req.latitude, "lon": req.longitude, "score": 0.43},
        {"lat": req.latitude - 0.01, "lon": req.longitude - 0.01, "score": 0.18},
    ]
    return {"tiles": predictions}
