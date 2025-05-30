import ee
import numpy as np
import rasterio
from rasterio.windows import Window
from PIL import Image
import os
import requests
import zipfile
import shutil
import matplotlib.pyplot as plt

# === Authenticate with Service Account ===
SERVICE_ACCOUNT = 'terrabite-earthengine@food-desert-app.iam.gserviceaccount.com'
KEY_PATH = '/etc/secrets/terrabite-earthengine.json'

try:
    credentials = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, KEY_PATH)
    ee.Initialize(credentials)
except Exception as e:
    print("❌ Earth Engine initialization failed:", e)

# === Paths ===
TEMP_DIR = './temp_tiles'
TIF_PATH = os.path.join(TEMP_DIR, 'exported_naip.tif')
TILE_OUTPUT_DIR = os.path.join(TEMP_DIR, 'tiles')
os.makedirs(TILE_OUTPUT_DIR, exist_ok=True)

# === Step 1: Export and download TIF (supports .zip or direct .tif)
def download_naip_tif(lat_min, lon_min, lat_max, lon_max):
    region = ee.Geometry.Rectangle([lon_min, lat_min, lon_max, lat_max])
    image = ee.ImageCollection("USDA/NAIP/DOQQ") \
        .filterBounds(region) \
        .filterDate('2021-01-01', '2023-12-31') \
        .mosaic() \
        .select(['R', 'G', 'B']) \
        .clip(region)

    download_url = image.getDownloadURL({
        'region': region,
        'scale': 4,
        'filePerBand': False,
        'format': 'GeoTIFF'
    })

    response = requests.get(download_url)
    if response.status_code != 200:
        raise RuntimeError(f"Download failed: {response.status_code}")

    content_type = response.headers.get("Content-Type", "")

    if "zip" in content_type:
        zip_path = os.path.join(TEMP_DIR, 'naip_download.zip')
        with open(zip_path, 'wb') as f:
            f.write(response.content)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(TEMP_DIR)

        # Find and rename .tif
        for file in os.listdir(TEMP_DIR):
            if file.endswith('.tif'):
                shutil.move(os.path.join(TEMP_DIR, file), TIF_PATH)
                break
        os.remove(zip_path)

    elif "tiff" in content_type or response.content[:4] == b'MM\x00*':
        with open(TIF_PATH, 'wb') as f:
            f.write(response.content)

    else:
        raise RuntimeError(f"Unexpected content type: {content_type}")

    print(f"✅ TIF saved to: {TIF_PATH}")

# === Step 2: Tile TIF into 256x256 PNGs
def tile_tif(input_tif_path, tile_size=256):
    tile_id = 0
    tile_data = []

    with rasterio.open(input_tif_path) as src:
        width, height = src.width, src.height
        transform = src.transform
        print(f"🧩 Image size: {width} x {height}")

        for y in range(0, height, tile_size):
            for x in range(0, width, tile_size):
                if x + tile_size <= width and y + tile_size <= height:
                    window = Window(x, y, tile_size, tile_size)
                    tile = src.read(window=window)

                    tile_rgb = tile.transpose(1, 2, 0).astype(np.float32)

                    for b in range(tile_rgb.shape[2]):
                        band = tile_rgb[:, :, b]
                        min_val = band.min()
                        max_val = band.max()
                        if max_val > min_val:
                            tile_rgb[:, :, b] = (band - min_val) / (max_val - min_val) * 255
                        else:
                            tile_rgb[:, :, b] = 0

                    tile_rgb = np.clip(tile_rgb, 0, 255).astype(np.uint8)

                    tile_path = os.path.join(TILE_OUTPUT_DIR, f"tile_{tile_id:04d}.png")
                    Image.fromarray(tile_rgb).save(tile_path)

                    # Calculate lat/lon of tile center
                    row_center = y + tile_size // 2
                    col_center = x + tile_size // 2
                    lon, lat = rasterio.transform.xy(transform, row_center, col_center)
                    
                    tile_data.append({
                        "path": tile_path,
                        "lat": lat,
                        "lon": lon
                    })
                    tile_id += 1

    print(f"✅ Tiling complete. {tile_id} tiles saved.")
    return tile_data

def generate_tiles(lat_min, lon_min, lat_max, lon_max):
    shutil.rmtree(TILE_OUTPUT_DIR, ignore_errors=True)
    os.makedirs(TILE_OUTPUT_DIR, exist_ok=True)

    download_naip_tif(lat_min, lon_min, lat_max, lon_max)
    return tile_tif(TIF_PATH)

