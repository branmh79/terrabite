import ee
import numpy as np
from PIL import Image
from io import BytesIO
import requests

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

# === Fetch RGB Tile from Earth Engine as NumPy Array ===
def fetch_rgb_image(lat_min, lon_min, lat_max, lon_max, scale=10):
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


    url = image.getThumbURL({
        'region': region,
        'dimensions': 256,
        'format': 'png',
        'min': 0,
        'max': 0.3  # adjust this if tiles look too dark/light
    })


    response = requests.get(url)
    if response.status_code != 200:
        raise RuntimeError(f"Image request failed with status {response.status_code}")

    img = Image.open(BytesIO(response.content)).convert("RGB")
    return np.array(img)
