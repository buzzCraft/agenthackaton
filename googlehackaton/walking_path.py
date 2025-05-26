import requests
import folium
from shapely.geometry import LineString, Point
from shapely.ops import substring
from pyproj import Transformer

SUPABASE_URL = 'https://mdokcoeymtjwssaldfpw.supabase.co'
SUPABASE_KEY = 'KEY'


def trim_segment_to_point(line, point, trim_start=True):
    """Trim a LineString from or to a given point"""
    proj = line.project(point, normalized=True)
    if trim_start:
        return substring(line, proj, 1.0, normalized=True)
    else:
        return substring(line, 0.0, proj, normalized=True)
    

def get_astar_path(start_lon, start_lat, end_lon, end_lat,
                   elrull_ok=["Tilgjengelig", "Delvis tilgjengelig"],
                   syn_ok=["Tilgjengelig", "Delvis tilgjengelig"]):
    url = f"{SUPABASE_URL}/rest/v1/rpc/find_astar_path_rullestol"

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    # Send arrays directly as Python lists
    payload = {
        "start_lon": start_lon,
        "start_lat": start_lat,
        "end_lon": end_lon,
        "end_lat": end_lat,
    }
    print("Payload:", payload)

    response = requests.post(url, headers=headers, json=payload)
    print("Response:", response.status_code, response.text)

    if response.status_code == 200:
        return response.json()
    else:
        print("Error:", response.status_code, response.text)
        return []