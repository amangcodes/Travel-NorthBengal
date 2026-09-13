import os
import csv
import math
import random
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or "your-project-id" in SUPABASE_URL:
    print("Error: Please set a valid SUPABASE_URL in your .env file.")
    exit(1)
if not SUPABASE_KEY or "your-anon-or-service-role" in SUPABASE_KEY:
    print("Error: Please set a valid SUPABASE_KEY in your .env file.")
    exit(1)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

CSV_PATH = "north_bengal_prices_INR.csv"

# ─── Coordinate data (from app.py) ────────────────────────────────────────────

DESTINATION_COORDS = {
    "darjeeling": {"lat": 27.0360, "lng": 88.2627},
    "gangtok":    {"lat": 27.3389, "lng": 88.6065},
    "kalimpong":  {"lat": 27.0594, "lng": 88.4693},
    "mirik":      {"lat": 26.8888, "lng": 88.1838},
    "lava":       {"lat": 27.0853, "lng": 88.6609},
    "kurseong":   {"lat": 26.8804, "lng": 88.2785},
    "dooars":     {"lat": 26.6975, "lng": 89.0075},
    "siliguri":   {"lat": 26.7271, "lng": 88.3953},
}

AREA_OFFSETS = {
    "city center":  {"dlat":  0.000, "dlng":  0.000},
    "mall road":    {"dlat":  0.008, "dlng":  0.004},
    "mg marg":      {"dlat": -0.005, "dlng":  0.007},
    "hill view":    {"dlat":  0.012, "dlng": -0.006},
    "tea garden":   {"dlat": -0.010, "dlng": -0.010},
    "forest area":  {"dlat":  0.015, "dlng":  0.012},
}

def _seed_for_id(place_id: str) -> float:
    return int(place_id) * 0.0001 if place_id.isdigit() else random.random()

def _jitter(base_lat: float, base_lng: float, area: str, place_id: str):
    offset = AREA_OFFSETS.get(area.lower().strip(), {"dlat": 0, "dlng": 0})
    seed = _seed_for_id(place_id)
    jlat = math.sin(seed * 12345) * 0.008
    jlng = math.cos(seed * 67890) * 0.008
    return {
        "latitude":  round(base_lat + offset["dlat"] + jlat, 6),
        "longitude": round(base_lng + offset["dlng"] + jlng, 6),
    }

def _get_map_category(csv_category):
    CSV_CATEGORY_MAP = {
        "Hotel":          "accommodation",
        "Homestay":       "accommodation",
        "Resort":         "accommodation",
        "Restaurant":     "food_beverage",
        "Cafe":           "food_beverage",
        "Activity":       "tourism_activity",
        "Attraction":     "tourism_activity",
        "Clothing Store": "shopping",
    }
    return CSV_CATEGORY_MAP.get(csv_category, "general")

def migrate():
    print(f"Starting migration from {CSV_PATH} to Supabase...")
    
    if not os.path.exists(CSV_PATH):
        print(f"Error: CSV file not found at {CSV_PATH}")
        return

    places = []
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            destination = row.get("Destination", "").strip().lower()
            csv_category = row.get("Category", "").strip()
            area = row.get("Area", "").strip()
            place_id = row.get("ID", "0").strip()
            
            # Calculate coordinates
            base = DESTINATION_COORDS.get(destination)
            coords = _jitter(base["lat"], base["lng"], area, place_id) if base else {"latitude": None, "longitude": None}

            # Prepare data for Supabase
            place = {
                "name":         row.get("Name", "Unknown").strip(),
                "category":     _get_map_category(csv_category),
                "csv_category": csv_category,
                "type":         row.get("Type", "").strip(),
                "destination":  destination,
                "area":         area,
                "price":        row.get("Price", "").strip(),
                "rating":       float(row.get("Rating", 0) or 0),
                "description":  row.get("Description", "").strip(),
                "latitude":     coords["latitude"],
                "longitude":    coords["longitude"]
            }
            places.append(place)

    print(f"Loaded {len(places)} records. Inserting into Supabase...")

    # Batch insert into Supabase
    chunk_size = 100
    success_count = 0
    for i in range(0, len(places), chunk_size):
        chunk = places[i:i + chunk_size]
        try:
            supabase.table("places").insert(chunk).execute()
            success_count += len(chunk)
            print(f"Uploaded: {success_count}/{len(places)}")
        except Exception as e:
            print(f"Error uploading chunk starting at index {i}: {e}")
            print("Make sure you have created the 'places' table in Supabase (see schema.sql)!")
            break

    print(f"Migration complete! Successfuly uploaded {success_count} records.")

if __name__ == "__main__":
    migrate()
