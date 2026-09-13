"""
North Bengal Local — Python Flask Backend
==========================================
Serves the static frontend and exposes REST API endpoints
that read from `north_bengal_prices_INR.csv`.

Run:
    pip install -r requirements.txt
    python app.py

Then open http://localhost:5000 in your browser.
"""

import csv
import os
import random
import math
import re
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# ─── App setup ──────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "north_bengal_prices_INR.csv")

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")
CORS(app)

# ─── Supabase setup ───────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

try:
    if not SUPABASE_URL or "your-project-id" in SUPABASE_URL:
        supabase = None
    else:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Failed to initialize Supabase: {e}")
    supabase = None

# ─── Coordinate database (approximate centers) ─────────────────────────────────

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

# Area offsets within a destination (so markers spread meaningfully)
AREA_OFFSETS = {
    "city center":  {"dlat":  0.000, "dlng":  0.000},
    "mall road":    {"dlat":  0.008, "dlng":  0.004},
    "mg marg":      {"dlat": -0.005, "dlng":  0.007},
    "hill view":    {"dlat":  0.012, "dlng": -0.006},
    "tea garden":   {"dlat": -0.010, "dlng": -0.010},
    "forest area":  {"dlat":  0.015, "dlng":  0.012},
}

# Map CSV "Category" values → map-level bucket
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

# ─── Data loading ───────────────────────────────────────────────────────────────

_cached_places = None          # populated on first request
_cached_cities = None
_cached_categories = None


def _seed_for_id(place_id: str) -> float:
    """Deterministic seed so the same place always gets the same jitter."""
    return int(place_id) * 0.0001 if place_id.isdigit() else random.random()


def _jitter(base_lat: float, base_lng: float, area: str, place_id: str):
    """
    Return coordinates with a deterministic offset based on area + small jitter
    so markers inside the same area don't overlap perfectly.
    """
    offset = AREA_OFFSETS.get(area.lower().strip(), {"dlat": 0, "dlng": 0})
    seed = _seed_for_id(place_id)
    # Small per-item jitter (≈ 200-500 m)
    jlat = math.sin(seed * 12345) * 0.008
    jlng = math.cos(seed * 67890) * 0.008
    return {
        "latitude":  round(base_lat + offset["dlat"] + jlat, 6),
        "longitude": round(base_lng + offset["dlng"] + jlng, 6),
    }

def _clean_name(name: str) -> str:
    """Remove trailing IDs (digits) from place names for a cleaner UI."""
    # Matches a space followed by one or more digits at the end of the string
    return re.sub(r'\s+\d+$', '', name.strip())

def _get_csv_places():
    """Read places from local CSV."""
    places = []
    if not os.path.exists(CSV_PATH):
        return []

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            destination = row.get("Destination", "").strip().lower()
            csv_category = row.get("Category", "").strip()
            area = row.get("Area", "").strip()
            map_category = CSV_CATEGORY_MAP.get(csv_category, "general")
            place_id = row.get("ID", "0").strip()

            base = DESTINATION_COORDS.get(destination)
            coords = _jitter(base["lat"], base["lng"], area, place_id) if base else None

            # Clean name (remove synthetic IDs like "Hotel 619")
            raw_name = row.get("Name", "Unknown").strip()
            clean_name = _clean_name(raw_name)
            
            # Hide generic descriptions
            description = row.get("Description", "").strip()
            if "great experience" in description.lower() or not description:
                description = f"Popular {csv_category.lower()} located in {area}."

            place = {
                "id":           f"csv_{place_id}",
                "name":         clean_name,
                "category":     map_category,
                "csvCategory":  csv_category,
                "type":         row.get("Type", "").strip(),
                "destination":  destination,
                "location":     area,
                "price":        row.get("Price", "").strip(),
                "rating":       float(row.get("Rating", 0) or 0),
                "description":  description,
                "coordinates":  coords,
                "source":       "csv"
            }
            places.append(place)
    return places

def _get_supabase_places():
    """Read places from Supabase."""
    if not supabase:
        return []
    try:
        response = supabase.table("places").select("*").execute()
        raw_places = response.data
        places = []
        for p in raw_places:
            destination = p.get("destination", "").strip().lower()
            area = p.get("area", "").strip()
            place_id = str(p.get("id", "0"))

            base = DESTINATION_COORDS.get(destination)
            coords = _jitter(base["lat"], base["lng"], area, place_id) if base else None

            # Clean name
            raw_name = p.get("name", "Unknown").strip()
            clean_name = _clean_name(raw_name)
            
            # Hide generic descriptions
            description = p.get("description", "").strip()
            csv_category = p.get("csv_category", "")
            if "great experience" in description.lower() or not description:
                description = f"Verified {csv_category.lower()} in {area}."

            place = {
                "id":           f"db_{place_id}",
                "name":         clean_name,
                "category":     p.get("category", "general"),
                "csvCategory":  csv_category,
                "type":         p.get("type", "").strip(),
                "destination":  destination,
                "location":     area,
                "price":        p.get("price", ""),
                "rating":       float(p.get("rating", 0) or 0),
                "description":  description,
                "coordinates":  coords,
                "source":       "supabase"
            }
            places.append(place)
        return places
    except Exception as e:
        print(f"Supabase fetch error: {e}")
        return []

def _load_data():
    """Fetch all places from both CSV and Supabase and merge them."""
    global _cached_places, _cached_cities, _cached_categories

    if _cached_places is not None:
        return

    csv_places = _get_csv_places()
    db_places = _get_supabase_places()
    
    # Merge and deduplicate by name + destination
    all_places = []
    seen = set()
    
    # Prioritize Supabase (DB) data over CSV data
    for p in (db_places + csv_places):
        key = (p["name"].lower(), p["destination"].lower())
        if key not in seen:
            all_places.append(p)
            seen.add(key)

    _cached_places = all_places
    
    # Build sorted lists for dropdowns
    city_set = set(p["destination"] for p in all_places)
    cat_set = set(p["category"] for p in all_places)
    
    _cached_cities = sorted(
        [{"value": c, "label": c.replace("_", " ").title()} for c in city_set],
        key=lambda x: x["label"],
    )
    _cached_categories = sorted(
        [{"value": c, "label": c.replace("_", " ").title()} for c in cat_set],
        key=lambda x: x["label"],
    )

def _load_csv_fallback():
    """Compatibility wrapper for old calls."""
    _load_data()


# ─── Static file routes ────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main website."""
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/map")
def map_page():
    """Serve the standalone map page."""
    return send_from_directory(BASE_DIR, "map_component.html")


# ─── API endpoints ──────────────────────────────────────────────────────────────

@app.route("/api/scraped-cities")
def api_scraped_cities():
    """Return list of destinations derived from the CSV."""
    _load_data()
    return jsonify({"cities": _cached_cities})


@app.route("/api/categories")
def api_categories():
    """Return list of map-level categories."""
    _load_data()
    return jsonify(_cached_categories)


@app.route("/api/map-markers")
def api_map_markers():
    """
    Return place markers for a given city.
    Query params:
        city     – destination name (required)
        category – filter by map category (optional)
        q        – text search (optional)
    """
    _load_data()

    city = request.args.get("city", "").strip().lower()
    category = request.args.get("category", "").strip().lower()
    q = request.args.get("q", "").strip().lower()

    results = _cached_places

    if city:
        results = [p for p in results if p["destination"] == city]
    if category:
        results = [p for p in results if p["category"] == category]
    if q:
        results = [
            p for p in results
            if q in (p["name"] + p["description"] + p["location"] + p.get("csvCategory", "")).lower()
        ]

    return jsonify(results)


@app.route("/api/geoapify-extract")
def api_geoapify_extract():
    """No-op stub — the original frontend calls this to trigger data refresh."""
    return jsonify({"status": "ok", "message": "Data loaded from CSV, no refresh needed."})


@app.route("/api/stats")
def api_stats():
    """Return aggregate stats from the CSV data."""
    _load_data()

    city = request.args.get("city", "").strip().lower()
    places = _cached_places
    if city:
        places = [p for p in places if p["destination"] == city]

    total = len(places)
    ratings = [p["rating"] for p in places if p["rating"] and p["rating"] > 0]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0.0

    prices = []
    for p in places:
        price_str = p.get("price", "")
        if price_str:
            num = "".join(c for c in price_str if c.isdigit())
            if num:
                prices.append(int(num))

    avg_price = round(sum(prices) / len(prices)) if prices else 0

    # Category breakdown
    cat_counts = {}
    for p in places:
        cat = p["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    # Destination breakdown (useful when no city filter)
    dest_counts = {}
    for p in places:
        dest = p["destination"]
        dest_counts[dest] = dest_counts.get(dest, 0) + 1

    return jsonify({
        "total_places":        total,
        "avg_rating":          avg_rating,
        "avg_price_inr":       avg_price,
        "category_breakdown":  cat_counts,
        "destination_breakdown": dest_counts,
    })


@app.route("/api/places/<place_id>")
def api_place_detail(place_id):
    """Return full details for a single place by ID."""
    _load_data()
    for p in _cached_places:
        if p["id"] == place_id:
            return jsonify(p)
    return jsonify({"error": "Place not found"}), 404


@app.route("/api/destinations")
def api_destinations():
    """
    Return rich destination info with counts and coordinates.
    Useful for the homepage destination cards.
    """
    _load_data()

    dest_map = {}
    for p in _cached_places:
        d = p["destination"]
        if d not in dest_map:
            coords = DESTINATION_COORDS.get(d, {})
            dest_map[d] = {
                "name":       d.replace("_", " ").title(),
                "value":      d,
                "latitude":   coords.get("lat"),
                "longitude":  coords.get("lng"),
                "total":      0,
                "categories": {},
            }
        dest_map[d]["total"] += 1
        cat = p["category"]
        dest_map[d]["categories"][cat] = dest_map[d]["categories"].get(cat, 0) + 1

    return jsonify(sorted(dest_map.values(), key=lambda x: x["name"]))


@app.route("/api/search")
def api_search():
    """
    Global search across all destinations.
    Query params:
        q – search query (required)
    """
    _load_data()

    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify([])

    results = []
    for p in _cached_places:
        haystack = " ".join([
            p["name"], p["description"], p["location"],
            p["destination"], p.get("csvCategory", ""), p.get("type", "")
        ]).lower()
        if q in haystack:
            results.append(p)

    # Cap at 100 results for performance
    return jsonify(results[:100])


from plan_trip_ai import generate_itinerary

@app.route("/api/plan-trip", methods=["POST"])
def api_plan_trip():
    """
    Simulated 'AI' trip planner.
    Parses prompt to find destination, days, and budget, then builds a smart itinerary
    using the actual places loaded from the CSV dataset.
    """
    _load_data()
    
    data = request.json or {}
    prompt = data.get("prompt", "").lower()

    result = generate_itinerary(prompt, _cached_cities, _cached_places, supabase)

    # Persistence: Save to Supabase if available
    if supabase and "title" in result and result.get("title") != "AI Brain Offline":
        try:
            supabase.table("trip_history").insert({
                "prompt": prompt,
                "response": result,
                "destination": result.get("destination"),
                "total_budget": result.get("total_budget", 0)
            }).execute()
        except Exception as e:
            print(f"Failed to save trip history: {e}")

    return jsonify(result)


# ─── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n  North Bengal Local Backend")
    print("  -------------------------")
    print(f"  CSV:      {CSV_PATH}")
    print(f"  Frontend: http://localhost:5000")
    print(f"  Map page: http://localhost:5000/map")
    print(f"  API docs: /api/scraped-cities, /api/categories, /api/map-markers?city=darjeeling")
    print()
    app.run(debug=True, host="0.0.0.0", port=5000)
