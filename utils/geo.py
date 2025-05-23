from typing import List, Dict
import math

def haversine_km_to_deg(km: float) -> float:
    """Approximate conversion of kilometers to degrees at the equator."""
    return km / 111.0  # ~111 km per degree latitude

def get_tile_grid(latitude: float, longitude: float, radius_km: float, tile_km: float = 2.56) -> List[Dict]:
    """Generate lat/lon bounding boxes for tiles covering a circular area."""
    deg_radius = haversine_km_to_deg(radius_km)
    deg_tile = haversine_km_to_deg(tile_km)

    lat_min = latitude - deg_radius
    lat_max = latitude + deg_radius
    lon_min = longitude - deg_radius
    lon_max = longitude + deg_radius

    tiles = []
    lat = lat_min
    tile_id = 0

    while lat < lat_max:
        lon = lon_min
        while lon < lon_max:
            tiles.append({
                "id": tile_id,
                "lat_min": lat,
                "lat_max": lat + deg_tile,
                "lon_min": lon,
                "lon_max": lon + deg_tile,
                "center_lat": lat + deg_tile / 2,
                "center_lon": lon + deg_tile / 2
            })
            lon += deg_tile
            tile_id += 1
        lat += deg_tile

    return tiles
