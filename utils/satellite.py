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
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        scale = 3 # 3.6 works for 5x5 grid
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
        scale = 3
        
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
def tile_tif(input_tif_path, tile_size=256, output_dir=None, prefix="tile"):
    tile_data = []

    with rasterio.open(input_tif_path) as src:
        width, height = src.width, src.height
        transform = src.transform
        print(f"🧩 Image size: {width} x {height}")

        # Grid of evenly spaced center points
        margin_x = int(width * 0.01)   # 4% margin left/right
        margin_y = int(height * 0.01)  # 4% margin top/bottom

        grid_x = np.linspace(margin_x + tile_size // 2, width - margin_x - tile_size // 2, 5, dtype=int)
        grid_y = np.linspace(margin_y + tile_size // 2, height - margin_y - tile_size // 2, 5, dtype=int)


        print(f"📐 Sampling 5x5 tile centers across full extent")

        tile_id = 0
        for y_center in grid_y:
            for x_center in grid_x:
                x = x_center - tile_size // 2
                y = y_center - tile_size // 2

                if x < 0 or y < 0 or x + tile_size > width or y + tile_size > height:
                    continue  # skip out-of-bounds tiles

                window = Window(x, y, tile_size, tile_size)
                tile = src.read(window=window)
                tile_rgb = tile.transpose(1, 2, 0).astype(np.float32)

                for b in range(tile_rgb.shape[2]):
                    band = tile_rgb[:, :, b]
                    min_val = np.percentile(band, 1)
                    max_val = np.percentile(band, 98)
                    max_val = min(max_val, 3500)
                    if max_val > min_val:
                        tile_rgb[:, :, b] = (band - min_val) / (max_val - min_val + 1e-6) * 255
                    else:
                        tile_rgb[:, :, b] = 0

                tile_rgb = np.clip(tile_rgb, 0, 255).astype(np.uint8)
                tile_path = os.path.join(output_dir, f"{prefix}_{tile_id:04d}.png")
                Image.fromarray(tile_rgb).save(tile_path)

                lon, lat = rasterio.transform.xy(transform, y_center, x_center)
                tile_data.append({
                    "path": tile_path,
                    "lat": lat,
                    "lon": lon
                })
                tile_id += 1

    print(f"✅ Evenly spaced tiling complete. {tile_id} tiles saved.")
    return tile_data


# === Step 3: Unified Function ===

def split_region(lat_min, lon_min, lat_max, lon_max, grid_size=2, shrink_ratio=0.96):
    lat_edges = np.linspace(lat_min, lat_max, grid_size + 1)
    lon_edges = np.linspace(lon_min, lon_max, grid_size + 1)

    subregions = []
    for i in range(grid_size):
        for j in range(grid_size):
            lat0 = lat_edges[i]
            lat1 = lat_edges[i + 1]
            lon0 = lon_edges[j]
            lon1 = lon_edges[j + 1]

            # shrink each subregion inward by a % margin
            lat_center = (lat0 + lat1) / 2
            lon_center = (lon0 + lon1) / 2
            lat_half = (lat1 - lat0) / 2 * shrink_ratio
            lon_half = (lon1 - lon0) / 2 * shrink_ratio

            sub_lat_min = lat_center - lat_half
            sub_lat_max = lat_center + lat_half
            sub_lon_min = lon_center - lon_half
            sub_lon_max = lon_center + lon_half

            subregions.append((sub_lat_min, sub_lon_min, sub_lat_max, sub_lon_max))
    return subregions


def process_subregion(idx, bounds, output_dir):
    s_lat_min, s_lon_min, s_lat_max, s_lon_max = bounds
    tif_path = os.path.join(output_dir, f'subregion_{idx}.tif')

    try:
        print(f"📦 Starting subregion {idx + 1} download...")
        download_tif(s_lat_min, s_lon_min, s_lat_max, s_lon_max, tif_path)
        tile_data = tile_tif(tif_path, tile_size=256, output_dir=output_dir, prefix=f"tile_s{idx}")

        return tile_data
    except Exception as e:
        print(f"❌ Subregion {idx + 1} failed: {e}")
        return []

def generate_tiles(lat_min, lon_min, lat_max, lon_max, output_dir):
    shutil.rmtree(output_dir, ignore_errors=True)
    os.makedirs(output_dir, exist_ok=True)

    subregions = split_region(lat_min, lon_min, lat_max, lon_max, grid_size=2)
    all_tile_data = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(process_subregion, idx, bounds, output_dir)
            for idx, bounds in enumerate(subregions)
        ]

        for future in as_completed(futures):
            all_tile_data.extend(future.result())

    print(f"✅ Parallel tiling complete. Total tiles: {len(all_tile_data)}")
    return all_tile_data

