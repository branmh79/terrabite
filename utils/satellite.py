import ee
import numpy as np
import rasterio
from rasterio.windows import Window
from PIL import Image
import os
import requests
import zipfile
import shutil
from shapely.geometry import Point, shape
import geopandas as gpd

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

# === US bounding box for NAIP coverage ===
US_BOUNDS = [-125, 24, -66, 50]  # Roughly the contiguous US

def is_in_us(lat, lon):
    return US_BOUNDS[1] <= lat <= US_BOUNDS[3] and US_BOUNDS[0] <= lon <= US_BOUNDS[2]

def mask_s2_clouds(image):
    qa = image.select('QA60')
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask).divide(10000)

# === Step 1: Export and download TIF ===
def download_tif(lat_min, lon_min, lat_max, lon_max, tif_path):
    region = ee.Geometry.Rectangle([lon_min, lat_min, lon_max, lat_max])
    center_lat = (lat_min + lat_max) / 2
    center_lon = (lon_min + lon_max) / 2

    if is_in_us(center_lat, center_lon):
        print("📍 Using NAIP imagery")
        image = ee.ImageCollection("USDA/NAIP/DOQQ") \
            .filterBounds(region) \
            .filterDate('2021-01-01', '2023-12-31') \
            .mosaic() \
            .select(['R', 'G', 'B']) \
            .clip(region)
        scale = 4
    else:
        print("🌍 Using Sentinel-2 SR Harmonized imagery")
        image = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
            .filterBounds(region) \
            .filterDate('2021-01-01', '2023-12-31') \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
            .map(mask_s2_clouds) \
            .median() \
            .select(['B4', 'B3', 'B2']) \
            .clip(region)
        scale = 4
        
    download_url = image.getDownloadURL({
        'region': region,
        'scale': scale,
        'filePerBand': False,
        'format': 'GeoTIFF'
    })

    response = requests.get(download_url)
    if response.status_code != 200:
        raise RuntimeError(f"Download failed: {response.status_code}")

    content_type = response.headers.get("Content-Type", "")

    if "zip" in content_type:
        zip_path = os.path.join(TEMP_DIR, 'download.zip')
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(TEMP_DIR)
        for file in os.listdir(TEMP_DIR):
            if file.endswith('.tif'):
                shutil.move(os.path.join(TEMP_DIR, file), tif_path)
                break
        os.remove(zip_path)
    elif "tiff" in content_type or response.content[:4] == b'MM\x00*':
        with open(tif_path, 'wb') as f:
            f.write(response.content)
    else:
        raise RuntimeError(f"Unexpected content type: {content_type}")

# === Step 2: Tile TIF into 256x256 PNGs ===
def tile_tif(input_tif_path, tile_size=256, output_dir=None):
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
                        min_val = np.percentile(band, 1)
                        max_val = np.percentile(band, 99)
                        max_val = min(max_val, 4000)  # Cap max value at 4000 for Sentinel
                        if max_val > min_val:
                            tile_rgb[:, :, b] = (band - min_val) / (max_val - min_val) * 255
                        else:
                            tile_rgb[:, :, b] = 0

                    tile_rgb = np.clip(tile_rgb, 0, 255).astype(np.uint8)

                    tile_path = os.path.join(output_dir, f"tile_{tile_id:04d}.png")

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

# === Step 3: Unified Function ===
def split_region(lat_min, lon_min, lat_max, lon_max, grid_size=2):
    lat_steps = np.linspace(lat_min, lat_max, grid_size + 1)
    lon_steps = np.linspace(lon_min, lon_max, grid_size + 1)

    subregions = []
    for i in range(grid_size):
        for j in range(grid_size):
            sub_lat_min = lat_steps[i]
            sub_lat_max = lat_steps[i + 1]
            sub_lon_min = lon_steps[j]
            sub_lon_max = lon_steps[j + 1]
            subregions.append((sub_lat_min, sub_lon_min, sub_lat_max, sub_lon_max))
    return subregions

def generate_tiles(lat_min, lon_min, lat_max, lon_max, output_dir):
    shutil.rmtree(output_dir, ignore_errors=True)
    os.makedirs(output_dir, exist_ok=True)

    all_tile_data = []
    subregions = split_region(lat_min, lon_min, lat_max, lon_max, grid_size=2)  # 2x2 = 4 parts

    for idx, (s_lat_min, s_lon_min, s_lat_max, s_lon_max) in enumerate(subregions):
        tif_path = os.path.join(output_dir, f'subregion_{idx}.tif')
        try:
            print(f"📦 Processing subregion {idx + 1}/{len(subregions)}...")
            download_tif(s_lat_min, s_lon_min, s_lat_max, s_lon_max, tif_path)
            tile_data = tile_tif(tif_path, tile_size=256, output_dir=output_dir)
            all_tile_data.extend(tile_data)
        except Exception as e:
            print(f"❌ Skipped subregion {idx + 1} due to error: {e}")

    print(f"✅ Finished generating tiles. Total: {len(all_tile_data)}")
    return all_tile_data
