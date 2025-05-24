import ee
import numpy as np
from PIL import Image
from io import BytesIO
import httpx

# === Service Account Auth ===
SERVICE_ACCOUNT = 'terrabite-earthengine@food-desert-app.iam.gserviceaccount.com'
KEY_PATH = '/etc/secrets/terrabite-earthengine.json'

try:
    credentials = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, KEY_PATH)
    ee.Initialize(credentials)
except Exception as e:
    print("❌ Earth Engine initialization failed:", e)

# === Cloud Masking Function ===
def mask_s2_clouds(image):
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(
           qa.bitwiseAnd(cirrusBitMask).eq(0))
    return image.updateMask(mask).divide(3000)

# === Async Fetch RGB Tile from Earth Engine ===
async def fetch_rgb_image_async(tile, scale=10):
    lat_min = tile["lat_min"]
    lon_min = tile["lon_min"]
    lat_max = tile["lat_max"]
    lon_max = tile["lon_max"]

    region = ee.Geometry.Rectangle([lon_min, lat_min, lon_max, lat_max])

    image = ee.ImageCollection("COPERNICUS/S2_SR") \
        .filter(ee.Filter.listContains('system:band_names', 'QA60')) \
        .filterBounds(region) \
        .filterDate('2021-01-01', '2022-12-31') \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10)) \
        .map(mask_s2_clouds) \
        .median() \
        .select(['B4', 'B3', 'B2']) \
        .rename(['R', 'G', 'B']) \
        .clip(region)

    try:
        url = image.getThumbURL({
            'region': region,
            'dimensions': 256,
            'format': 'png',
            'min': 0,
            'max': 0.3
        })
    except Exception as e:
        print(f"❌ Error generating URL for tile {tile}: {e}")
        return None

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content)).convert("RGB")
            return np.array(img)
    except Exception as e:
        print(f"❌ Failed to download or decode image for tile {tile}: {e}")
        return None
