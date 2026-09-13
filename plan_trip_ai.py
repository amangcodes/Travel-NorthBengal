"""
NB Local — AI Trip Planner Brain v3.0
======================================
A sophisticated RAG-powered travel planning engine for North Bengal & Sikkim.

Features:
  - TF-IDF semantic retrieval for place matching
  - Smart budget allocation (accommodation / food / activities)
  - Preference detection (adventure, relaxation, food-focused, family, etc.)
  - Season & weather awareness
  - Conversational memory via Supabase trip_history
  - Strict geographic accuracy (only recommends real, verified places)
  - Cost optimization with running totals
  - Multi-destination trip support
  - Intelligent fallback when LLM is unavailable
"""

import os
import re
import json
import random
from datetime import datetime
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import requests
import groq
import difflib

# Load environment variables
load_dotenv()

# ─── Groq Client ───────────────────────────────────────────────────────────────

def get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or api_key == "your-free-groq-api-key-here":
        return None
    try:
        return groq.Groq(api_key=api_key)
    except Exception:
        return None


def query_local_default_model(base_url):
    try:
        response = requests.get(f"{base_url}/v1/models", timeout=10)
        response.raise_for_status()
        data = response.json()
        models = [m.get("id") for m in data.get("data", []) if m.get("id") and "embed" not in m.get("id")]
        return models[0] if models else None
    except Exception as e:
        print(f"Local LLM model discovery failed: {e}")
        return None


def get_local_llm_settings():
    """Return local model endpoint config if configured."""
    base_url = os.environ.get("LOCAL_LLM_URL") or os.environ.get("OPENAI_API_BASE") or "http://127.0.0.1:1234"
    base_url = base_url.rstrip("/")
    model = os.environ.get("LOCAL_LLM_MODEL") or os.environ.get("OPENAI_MODEL")
    if not model:
        model = query_local_default_model(base_url) or "google/gemma-4-e2b"
    api_key = os.environ.get("LOCAL_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    return {
        "base_url": base_url,
        "model": model,
        "api_key": api_key,
    }


def call_local_llm(messages, temperature=0.7, max_tokens=2000):
    settings = get_local_llm_settings()
    if not settings:
        return None
    url = f"{settings['base_url']}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if settings["api_key"]:
        headers["Authorization"] = f"Bearer {settings['api_key']}"
    payload = {
        "model": settings["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()

# ─── Price utility ──────────────────────────────────────────────────────────────

def extract_price(price_str):
    """Extract numeric INR value from a string like '1500 INR'."""
    num = "".join(c for c in str(price_str) if c.isdigit())
    return int(num) if num else 0

# ─── Destination Knowledge Base ─────────────────────────────────────────────────

DESTINATION_GUIDE = {
    "darjeeling": {
        "tagline": "The Queen of Hills",
        "highlights": "Tiger Hill sunrise, Batasia Loop, tea garden walks, Himalayan Mountaineering Institute, Peace Pagoda, toy train heritage ride",
        "best_season": "March-May (spring blooms), Oct-Nov (clear Kanchenjunga views)",
        "avoid": "June-Sept (heavy monsoons)",
        "vibe": "colonial charm, panoramic Himalayan views, heritage railways",
        "tip": "Book Tiger Hill jeep a day in advance. Carry layers — morning fog is chilly even in summer."
    },
    "gangtok": {
        "tagline": "Gateway to Sikkim",
        "highlights": "MG Marg promenade, Rumtek Monastery, Tsomgo Lake, Nathula Pass (permit needed), Hanuman Tok, Tashi viewpoint",
        "best_season": "March-June, Sept-Dec",
        "avoid": "July-Aug (landslides on highways)",
        "vibe": "clean mountain city, Buddhist monasteries, vibrant MG Marg nightlife",
        "tip": "Get an Inner Line Permit for Nathula. MG Marg is car-free and perfect for evening walks."
    },
    "kalimpong": {
        "tagline": "The Orchid Paradise",
        "highlights": "Deolo Hill, Durpin Monastery, Cactus Nursery, Dr. Graham's Homes, Mangal Dham, pine forests",
        "best_season": "Oct-March (clear skies, cool weather)",
        "avoid": "July-Aug (monsoons)",
        "vibe": "quiet, offbeat, artistic, nurseries and gardens",
        "tip": "Visit the flower markets early morning. Kalimpong cheese and noodles are local specialties."
    },
    "mirik": {
        "tagline": "The Hidden Gem of Darjeeling",
        "highlights": "Sumendu Lake, Mirik Monastery, tea gardens, boating, Rameetay Dara sunrise",
        "best_season": "Oct-April",
        "avoid": "July-Aug",
        "vibe": "serene lake town, romantic, slow travel",
        "tip": "Take a horse ride around the lake or rent a boat at sunset. The pony trail is beautiful."
    },
    "dooars": {
        "tagline": "The Gateway to Eastern Himalayas",
        "highlights": "Jaldapara National Park (rhino safari), Gorumara, Chapramari, Buxa Fort, Jayanti river",
        "best_season": "Oct-March (dry, ideal for wildlife)",
        "avoid": "June-Sept (park closures during monsoon)",
        "vibe": "wildlife, jungle, rivers, tribal culture",
        "tip": "Book elephant or jeep safari at Jaldapara well in advance. Carry binoculars."
    },
    "lava": {
        "tagline": "The Himalayan Hideout",
        "highlights": "Neora Valley National Park, Lava Monastery, Changey Waterfalls, Rishyap viewpoint, virgin forests",
        "best_season": "Oct-March (snow possible Dec-Feb)",
        "avoid": "July-Aug",
        "vibe": "remote, pristine forest, birding paradise, snow country",
        "tip": "Rishyap (10km away) has the best Kanchenjunga views. Carry warm clothes year-round."
    },
    "kurseong": {
        "tagline": "The Land of White Orchids",
        "highlights": "Eagle's Craig, Kettle Valley, Makaibari tea estate, Dow Hill, Chimney heritage house",
        "best_season": "Oct-April",
        "avoid": "July-Aug",
        "vibe": "offbeat, misty, tea trails, quiet hills",
        "tip": "Visit Makaibari for a real tea-plucking experience. Dow Hill forest walk is hauntingly beautiful."
    }
}

# ─── Real Landmark Database (verified, actual places) ───────────────────────────
# These are REAL places with accurate details — used to enrich generic CSV data.

REAL_LANDMARKS = {
    "darjeeling": [
        {"name": "Tiger Hill Sunrise Point", "type": "Viewpoint", "price": "Free (Jeep: 300 INR)", "desc": "Famous sunrise viewpoint at 2,590m with panoramic Kanchenjunga views. Arrive by 4:30 AM."},
        {"name": "Batasia Loop & War Memorial", "type": "Heritage", "price": "Free", "desc": "Iconic spiral railway loop with a war memorial garden. The toy train circles through here."},
        {"name": "Himalayan Mountaineering Institute (HMI)", "type": "Museum", "price": "100 INR", "desc": "Museum dedicated to mountaineering with Everest exhibits. Founded by Tenzing Norgay."},
        {"name": "Peace Pagoda (Japanese Temple)", "type": "Temple", "price": "Free", "desc": "Beautiful white pagoda built by Japanese Buddhists with stunning mountain views."},
        {"name": "Darjeeling Himalayan Railway (Toy Train)", "type": "Heritage Ride", "price": "100-1500 INR", "desc": "UNESCO World Heritage narrow-gauge railway. Joy rides from Darjeeling to Ghum."},
        {"name": "Happy Valley Tea Estate", "type": "Tea Garden", "price": "100 INR", "desc": "One of the oldest tea estates. Guided tour of plucking, processing, and tasting."},
        {"name": "Padmaja Naidu Himalayan Zoological Park", "type": "Zoo", "price": "100 INR", "desc": "Home to red pandas, snow leopards, and Himalayan wolves. Located near HMI."},
        {"name": "Observatory Hill (Mahakal Temple)", "type": "Viewpoint/Temple", "price": "Free", "desc": "Sacred hilltop with Hindu-Buddhist shrine and 360-degree mountain views."},
        {"name": "Chowrasta (Mall Road)", "type": "Promenade", "price": "Free", "desc": "Heart of Darjeeling — open pedestrian square with mountain views, ponies, and shops."},
        {"name": "Rock Garden & Ganga Maya Park", "type": "Garden", "price": "50 INR", "desc": "Terraced garden with waterfalls and streams. Beautiful walk down from Darjeeling town."},
        {"name": "Glenary's Bakery & Cafe", "type": "Restaurant", "price": "300-600 INR", "desc": "Iconic Darjeeling bakery since 1935. Famous for pastries, breakfast, and valley views."},
        {"name": "Keventers (The Original)", "type": "Cafe", "price": "100-250 INR", "desc": "Historic cafe on Mall Road. Famous for milkshakes and colonial-era ambiance."},
        {"name": "Kunga Restaurant", "type": "Restaurant", "price": "150-350 INR", "desc": "Best momos and Tibetan thukpa in Darjeeling. Local favorite near Chowrasta."},
    ],
    "gangtok": [
        {"name": "MG Marg (Mahatma Gandhi Marg)", "type": "Promenade", "price": "Free", "desc": "Car-free pedestrian street with cafes, shops, and mountain views. Heart of Gangtok."},
        {"name": "Rumtek Monastery", "type": "Monastery", "price": "Free", "desc": "Largest monastery in Sikkim. Seat of the Karmapa. Stunning architecture and peaceful grounds."},
        {"name": "Tsomgo (Changu) Lake", "type": "Lake", "price": "200 INR (permit)", "desc": "Sacred glacial lake at 3,753m. Frozen in winter. Yak rides available."},
        {"name": "Nathula Pass", "type": "Border Pass", "price": "200 INR (permit)", "desc": "Indo-China border at 4,310m. Open Wed-Sun. Indian passport required."},
        {"name": "Hanuman Tok", "type": "Temple/Viewpoint", "price": "Free", "desc": "Hilltop temple maintained by Indian Army. Spectacular Kanchenjunga views."},
        {"name": "Enchey Monastery", "type": "Monastery", "price": "Free", "desc": "200-year-old hilltop monastery with colorful murals and mountain views."},
        {"name": "Tashi Viewpoint", "type": "Viewpoint", "price": "Free", "desc": "Panoramic viewpoint for Mt. Kanchenjunga. Best in early morning."},
        {"name": "Do Drul Chorten (Stupa)", "type": "Monument", "price": "Free", "desc": "Large Buddhist stupa with 108 prayer wheels. Peaceful meditation spot."},
        {"name": "Lall Market", "type": "Market", "price": "Free", "desc": "Bustling local market near MG Marg. Fresh produce, spices, and handcrafts."},
        {"name": "The Coffee Shop (MG Marg)", "type": "Cafe", "price": "150-300 INR", "desc": "Popular cafe on MG Marg with good coffee and Sikkimese snacks."},
        {"name": "Taste of Tibet", "type": "Restaurant", "price": "150-350 INR", "desc": "Authentic Tibetan cuisine — momos, thukpa, and tingmo."},
    ],
    "kalimpong": [
        {"name": "Deolo Hill", "type": "Viewpoint", "price": "Free", "desc": "Highest point in Kalimpong at 1,704m. 360-degree views of Teesta valley and Kanchenjunga."},
        {"name": "Durpin Monastery (Zang Dhok Palri)", "type": "Monastery", "price": "Free", "desc": "Hilltop monastery consecrated by the Dalai Lama. Houses rare Buddhist scriptures."},
        {"name": "Pine View Nursery & Cactus Garden", "type": "Garden", "price": "20 INR", "desc": "Famous nursery with 1,500+ cactus species. Kalimpong's horticultural pride."},
        {"name": "Dr. Graham's Homes", "type": "Heritage", "price": "Free", "desc": "Historic mission school with beautiful stone buildings and chapel. Founded 1900."},
        {"name": "Mangal Dham", "type": "Temple", "price": "Free", "desc": "Ornate Krishna temple with detailed marble work and gardens."},
        {"name": "Kalimpong Arts & Crafts Centre", "type": "Craft Centre", "price": "Free", "desc": "Local handicrafts — Tibetan carpets, woodwork, traditional textiles."},
    ],
    "mirik": [
        {"name": "Sumendu Lake", "type": "Lake", "price": "Boating: 100-200 INR", "desc": "Heart of Mirik. Beautiful 1.25km lake with boating, horse rides, and a footbridge."},
        {"name": "Mirik Monastery (Bokar Gompa)", "type": "Monastery", "price": "Free", "desc": "Peaceful Buddhist monastery on hilltop. Meditation courses available."},
        {"name": "Rameetay Dara", "type": "Viewpoint", "price": "Free", "desc": "Sunrise viewpoint 5km from Mirik. Views of Kanchenjunga and Everest on clear days."},
        {"name": "Mirik Tea Gardens (Thurbo/Gopaldhara)", "type": "Tea Garden", "price": "Free", "desc": "Walk through lush tea estates surrounding the lake. Best in morning mist."},
        {"name": "Orange Orchards", "type": "Nature", "price": "Free", "desc": "Visit orange orchards in season (Nov-Jan). Fresh oranges and mountain views."},
    ],
    "dooars": [
        {"name": "Jaldapara National Park", "type": "Wildlife/Safari", "price": "Elephant Safari: 700 INR, Jeep: 1500 INR", "desc": "Famous for one-horned Indian rhinoceros. Elephant safari is the highlight."},
        {"name": "Gorumara National Park", "type": "Wildlife/Safari", "price": "Jeep Safari: 1200 INR", "desc": "Rich biodiversity — Indian bison, elephants, deer. Watchtower safaris available."},
        {"name": "Buxa Fort & Tiger Reserve", "type": "Heritage/Wildlife", "price": "100 INR", "desc": "Historic fort with trekking trails. Part of Buxa Tiger Reserve."},
        {"name": "Chapramari Wildlife Sanctuary", "type": "Wildlife", "price": "50 INR", "desc": "Smaller, quieter sanctuary. Great for birdwatching and elephant sightings."},
        {"name": "Jayanti (Buxa)", "type": "River/Village", "price": "Free", "desc": "Indo-Bhutan border village with crystal-clear Jayanti river. Swimming and camping."},
        {"name": "Murti River", "type": "River", "price": "Free", "desc": "Popular riverside camping and picnic spot. River rafting in season."},
    ],
    "lava": [
        {"name": "Neora Valley National Park", "type": "National Park", "price": "100 INR", "desc": "Virgin forest with red pandas, black bears. Guided treks available."},
        {"name": "Lava Monastery (Kagyu Thekchen Ling)", "type": "Monastery", "price": "Free", "desc": "Colorful Buddhist monastery in the heart of Lava. Peaceful prayer halls."},
        {"name": "Changey Waterfalls", "type": "Waterfall", "price": "Free", "desc": "Scenic waterfall 5km from Lava. Short trek through pine forests."},
        {"name": "Rishyap Viewpoint", "type": "Viewpoint", "price": "Free", "desc": "10km from Lava. Best Kanchenjunga panorama in the region. Snow in winter."},
        {"name": "Lava Forest Nature Walk", "type": "Nature Walk", "price": "Free", "desc": "Birding trails through pristine forests of oak, pine, and rhododendron."},
    ],
    "kurseong": [
        {"name": "Eagle's Craig", "type": "Viewpoint", "price": "Free", "desc": "Panoramic viewpoint with sweeping views of the plains and hills."},
        {"name": "Makaibari Tea Estate", "type": "Tea Estate", "price": "200 INR", "desc": "World's first organic tea garden. Tea plucking experience and factory tour."},
        {"name": "Kettle Valley", "type": "Nature", "price": "Free", "desc": "Beautiful valley with streams and forests. Easy walking trails."},
        {"name": "Dow Hill", "type": "Forest", "price": "Free", "desc": "Dense forest area with eco park and nature trails. Misty and atmospheric."},
        {"name": "Chimney (Heritage House)", "type": "Heritage", "price": "Free", "desc": "Historic British-era house converted into a heritage walk."},
        {"name": "Ambotia Shiva Temple", "type": "Temple", "price": "Free", "desc": "Hilltop temple surrounded by tea gardens with mountain views."},
    ],
}

# ─── Preference Detection ──────────────────────────────────────────────────────

PREFERENCE_KEYWORDS = {
    "adventure":    ["adventure", "trek", "trekking", "hiking", "rafting", "safari", "explore", "thrill", "sport"],
    "relaxation":   ["relax", "peaceful", "calm", "chill", "spa", "lazy", "rest", "quiet", "slow", "leisure"],
    "food":         ["food", "foodie", "eat", "cuisine", "restaurant", "cafe", "taste", "culinary", "dining", "street food"],
    "culture":      ["culture", "monastery", "temple", "heritage", "history", "museum", "tradition", "local life"],
    "nature":       ["nature", "waterfall", "lake", "forest", "garden", "scenic", "viewpoint", "sunrise", "sunset", "mountain"],
    "family":       ["family", "kids", "children", "safe", "easy", "comfortable"],
    "budget":       ["cheap", "budget", "affordable", "economical", "backpacker", "low cost", "save money"],
    "luxury":       ["luxury", "premium", "best", "top", "5 star", "five star", "exclusive", "upscale"],
    "romantic":     ["romantic", "couple", "honeymoon", "anniversary", "love", "date"],
    "shopping":     ["shopping", "shop", "market", "souvenir", "buy", "handicraft"],
}

def detect_preferences(prompt_lower):
    """Detect travel preferences from the user's prompt."""
    detected = []
    for pref, keywords in PREFERENCE_KEYWORDS.items():
        if any(kw in prompt_lower for kw in keywords):
            detected.append(pref)
    return detected if detected else ["nature", "culture"]  # sensible default

def detect_season_context():
    """Get current season context for North Bengal."""
    month = datetime.now().month
    if month in [3, 4, 5]:
        return "spring", "Spring is wonderful — rhododendrons are blooming, clear mountain views, pleasant 12-22C weather."
    elif month in [6, 7, 8, 9]:
        return "monsoon", "It's monsoon season — roads may be affected. Carry rain gear. Avoid Nathula, Dooars safaris may be closed."
    elif month in [10, 11]:
        return "autumn", "Autumn is the BEST time — crystal clear Kanchenjunga views, festivals (Dussehra, Diwali), perfect trekking weather."
    else:
        return "winter", "Winter brings snow to Lava/Sandakphu, cozy foggy Darjeeling, and fewer tourists. Carry heavy woolens."

# ─── RAG Retriever ──────────────────────────────────────────────────────────────

_vectorizer = None
_place_documents = []
_place_objects = []
_tfidf_matrix = None

def _initialize_retriever(places):
    global _vectorizer, _place_documents, _place_objects, _tfidf_matrix
    if _tfidf_matrix is not None:
        return

    _place_objects = places
    _place_documents = []

    for p in places:
        doc = f"{p['name']} {p['destination']} {p['category']} {p.get('csvCategory','')} {p['location']} {p['description']} {p['price']}"
        _place_documents.append(doc.lower())

    _vectorizer = TfidfVectorizer(stop_words='english')
    _tfidf_matrix = _vectorizer.fit_transform(_place_documents)

def retrieve_relevant(query, destination, k=20):
    """Retrieve top K places matching query AND filtered to a specific destination."""
    query_vec = _vectorizer.transform([query.lower()])
    similarities = cosine_similarity(query_vec, _tfidf_matrix).flatten()

    scored = []
    for idx, score in enumerate(similarities):
        if _place_objects[idx]["destination"] == destination and score > 0.01:
            scored.append((score, _place_objects[idx]))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:k]]

# ─── Conversation Memory ───────────────────────────────────────────────────────

def get_recent_history(supabase_client, limit=5):
    """Retrieve recent trip planning history for conversational context."""
    if not supabase_client:
        return ""
    try:
        response = (supabase_client.table("trip_history")
                    .select("prompt", "destination", "total_budget")
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute())
        history = response.data
        if not history:
            return ""

        lines = ["Previous conversations (for context, do NOT repeat these plans):"]
        for h in reversed(history):
            budget_str = f", Budget: {h.get('total_budget', 'N/A')} INR" if h.get('total_budget') else ""
            lines.append(f"  - \"{h['prompt']}\" -> {h.get('destination', 'N/A')}{budget_str}")
        return "\n".join(lines)
    except Exception:
        return ""

# ─── Place Deduplication & Enrichment ───────────────────────────────────────────

def _deduplicate_places(dest_places):
    """
    Deduplicate places by name within a destination.
    Keeps the highest-rated version of each unique name.
    Enriches generic names (e.g., 'Lake') with area context.
    """
    GENERIC_NAMES = {"lake", "monastery", "trekking", "waterfall", "view point",
                     "toy train ride", "boating", "hiking", "temple", "park",
                     "garden", "museum", "market", "bridge"}

    best = {}  # key = enriched_name_lower → place dict
    for p in dest_places:
        name = p["name"]
        area = p.get("location", "").strip()

        # Enrich generic names with area
        if name.lower() in GENERIC_NAMES and area:
            enriched = f"{name} ({area})"
        else:
            enriched = name

        key = enriched.lower()
        if key not in best or p["rating"] > best[key]["rating"]:
            enriched_place = dict(p)
            enriched_place["name"] = enriched
            best[key] = enriched_place

    return list(best.values())


# ─── Smart Context Builder ──────────────────────────────────────────────────────

def build_smart_context(dest, places, budget, days, preferences):
    """
    Build an intelligent, budget-aware context string for the LLM.
    Deduplicates CSV places, injects real landmarks, and annotates budgets.
    """
    dest_places = [p for p in places if p["destination"] == dest]
    daily_budget = budget // max(days, 1)

    # Budget allocation strategy
    accom_budget = int(daily_budget * 0.45)   # 45% on stay
    food_budget  = int(daily_budget * 0.30)   # 30% on food (3 meals)
    activity_budget = int(daily_budget * 0.15) # 15% on paid activities
    misc_budget = int(daily_budget * 0.10)     # 10% buffer

    # DEDUPLICATE first — the CSV has dozens of copies of each name
    unique_places = _deduplicate_places(dest_places)

    # Categorize and sort
    accommodations = sorted(
        [p for p in unique_places if p["category"] == "accommodation" and extract_price(p.get("price", "")) > 0],
        key=lambda p: (-p["rating"], extract_price(p.get("price", "")))
    )
    foods = sorted(
        [p for p in unique_places if p["category"] == "food_beverage" and extract_price(p.get("price", "")) > 0],
        key=lambda p: (-p["rating"], extract_price(p.get("price", "")))
    )
    activities = sorted(
        [p for p in unique_places if p["category"] == "tourism_activity"],
        key=lambda p: -p["rating"]
    )
    shopping = sorted(
        [p for p in unique_places if p["category"] == "shopping"],
        key=lambda p: -p["rating"]
    )

    # Filter by budget
    affordable_stays = [p for p in accommodations if extract_price(p.get("price", "")) <= accom_budget]
    if not affordable_stays:
        affordable_stays = accommodations[:5]

    per_meal_budget = food_budget // 3
    affordable_food = [p for p in foods if extract_price(p.get("price", "")) <= per_meal_budget]
    if not affordable_food:
        affordable_food = foods[:10]

    # Preference boosting
    activity_count = 12 if "adventure" in preferences else 8
    food_count = 12 if "food" in preferences else 8
    shop_count = 4 if "shopping" in preferences else 2

    # Build context
    lines = []
    lines.append(f"=== VERIFIED PLACES IN {dest.upper()} ===")
    lines.append(f"(Budget: {budget} INR for {days} days, ~{daily_budget} INR/day)")
    lines.append(f"Budget split: Stay ~{accom_budget}/night | Food ~{food_budget}/day | Activities ~{activity_budget}/day")

    # ── REAL LANDMARKS (highest priority — use these by name) ──
    landmarks = REAL_LANDMARKS.get(dest, [])
    if landmarks:
        lines.append(f"\n[MUST-VISIT LANDMARKS — use exact names]")
        for lm in landmarks:
            lines.append(f"  ★ {lm['name']} | {lm['type']} | {lm['price']} | {lm['desc']}")

    def _fmt(p):
        price = p.get("price", "")
        return f"  {p['name']} | {p['location']} | {price if price else 'Free'} | Rating: {p['rating']}/5"

    lines.append(f"\n[ACCOMMODATION OPTIONS] (budget ~{accom_budget}/night)")
    for p in affordable_stays[:6]:
        lines.append(_fmt(p))

    lines.append(f"\n[FOOD & CAFES] (budget ~{per_meal_budget}/meal)")
    for p in affordable_food[:food_count]:
        lines.append(_fmt(p))

    lines.append(f"\n[OTHER ACTIVITIES] (many are free)")
    for p in activities[:activity_count]:
        lines.append(_fmt(p))

    if shopping:
        lines.append(f"\n[SHOPPING]")
        for p in shopping[:shop_count]:
            lines.append(_fmt(p))

    return "\n".join(lines)

# ─── Prompt Parsing ─────────────────────────────────────────────────────────────

def parse_prompt(prompt_lower, cities):
    """
    Extract destination, days, budget, and preferences from natural language.
    Returns a dict with all parsed fields.
    """
    city_values = [c["value"] for c in cities]

    # ── Greeting / chat detection ──
    greetings = ["hi", "hello", "hey", "who are you", "how are you", "help",
                 "what can you do", "namaste", "good morning", "good evening",
                 "thanks", "thank you", "bye", "ok"]
    is_chat = (any(g == prompt_lower.strip() for g in greetings)
               or len(prompt_lower.split()) < 3)

    # ── Days ──
    days_match = re.search(r"(\d+)\s*(?:day|night)", prompt_lower)
    raw_days = int(days_match.group(1)) if days_match else (0 if is_chat else 3)
    days = min(10, max(0, raw_days))  # cap at 10 for a single destination

    # ── Budget ──
    budget_match = re.search(r"(?:under|budget|within|below|max|upto|up to|less than|not more than)\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)", prompt_lower)
    if not budget_match:
        budget_match = re.search(r"(?:₹|rs\.?|inr)\s*(\d[\d,]*)", prompt_lower)
    if budget_match:
        budget = int(budget_match.group(1).replace(",", ""))
    else:
        # Look for big numbers that are likely budgets (exclude the days number)
        days_num = raw_days if days_match else -1
        all_numbers = [(int(n.replace(",", ""))) for n in re.findall(r"\d[\d,]*", prompt_lower)]
        possible_budgets = [n for n in all_numbers if n >= 500 and n != days_num]
        budget = possible_budgets[-1] if possible_budgets else (days * 2000 if days > 0 else 5000)

    # ── Destination ──
    matched_dest = None

    # Exact substring match
    for city in sorted(city_values, key=len, reverse=True):  # longest first to avoid 'lava' matching inside another word
        if re.search(r'\b' + re.escape(city) + r'\b', prompt_lower):
            matched_dest = city
            break

    # Fuzzy match fallback
    if not matched_dest and not is_chat:
        words = re.findall(r'\b[a-z]{3,}\b', prompt_lower)
        for word in words:
            matches = difflib.get_close_matches(word, city_values, n=1, cutoff=0.75)
            if matches:
                matched_dest = matches[0]
                break

    # ── Preferences ──
    preferences = detect_preferences(prompt_lower)

    # ── People count ──
    people_match = re.search(r"(\d+)\s*(?:people|person|pax|members|adults)", prompt_lower)
    people = int(people_match.group(1)) if people_match else 1

    return {
        "destination": matched_dest,
        "days": days,
        "raw_days": raw_days,
        "budget": budget,
        "preferences": preferences,
        "people": people,
        "is_chat": is_chat,
    }

# ─── Main Brain ─────────────────────────────────────────────────────────────────

def generate_itinerary(prompt, cities, places, supabase_client=None):
    """
    NB Local AI Brain v3 — RAG + LLM trip planner with memory, preferences, and budget intelligence.
    """
    _initialize_retriever(places)
    prompt_lower = prompt.lower().strip()

    # ── Parse everything ──
    parsed = parse_prompt(prompt_lower, cities)
    dest = parsed["destination"]
    days = parsed["days"]
    raw_days = parsed["raw_days"]
    budget = parsed["budget"]
    preferences = parsed["preferences"]
    people = parsed["people"]
    is_chat = parsed["is_chat"]

    # ── Memory ──
    history_context = get_recent_history(supabase_client) if supabase_client else ""

    # ── Season ──
    season_name, season_advice = detect_season_context()

    # ── Destination guide ──
    city_values = [c["value"] for c in cities]
    valid_cities_list = ", ".join([c["label"] for c in cities])

    # ── Handle unsupported destinations ──
    if not dest and not is_chat:
        return {
            "title": "Destination Not Supported",
            "destination": "Unknown",
            "total_budget": budget,
            "itinerary": [{
                "day": 1,
                "section": "I'm your North Bengal expert!",
                "activities": [
                    "I specialize exclusively in the North Bengal and Sikkim regions.",
                    f"I can plan amazing trips to: {valid_cities_list}.",
                    "Try something like: 'Plan a 3-day adventure trip to Darjeeling under 8000 INR'"
                ]
            }]
        }

    dest = dest if dest else "darjeeling"
    dest_info = DESTINATION_GUIDE.get(dest, {})
    city_label = next((c["label"] for c in cities if c["value"] == dest), dest.title())

    # ── Handle chat/greetings ──
    if is_chat:
        chat_system = f"""You are 'NB Local', a warm, knowledgeable AI travel expert for North Bengal & Sikkim.
You MUST output raw JSON only. No markdown.
Available destinations: {valid_cities_list}.
Current season: {season_name} — {season_advice}

{history_context}

Respond conversationally but always steer towards trip planning.
Output format:
{{"title":"NB Local","destination":"","total_budget":0,"itinerary":[{{"day":1,"section":"Assistant","activities":["your message"]}}]}}"""

        local_resp = None
        try:
            local_resp = call_local_llm([
                {"role": "system", "content": chat_system},
                {"role": "user", "content": prompt}
            ], temperature=0.7, max_tokens=500)
        except Exception:
            local_resp = None

        if local_resp:
            try:
                text = local_resp["choices"][0]["message"]["content"].strip()
                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text)
                return json.loads(text)
            except Exception:
                pass

        client = get_groq_client()
        if client:
            try:
                resp = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": chat_system},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=500,
                )
                text = resp.choices[0].message.content.strip()
                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text)
                return json.loads(text)
            except Exception:
                pass

        return {
            "title": "NB Local",
            "destination": "",
            "total_budget": 0,
            "itinerary": [{
                "day": 1,
                "section": "Welcome!",
                "activities": [
                    f"Hi! I'm NB Local, your personal travel expert for North Bengal & Sikkim.",
                    f"I can plan trips to {valid_cities_list}.",
                    f"Current season tip: {season_advice}",
                    "Try: 'Plan a 3-day family trip to Gangtok under 10000'"
                ]
            }]
        }

    # ── Duration sanity check (before budget) ──
    # If user asked for way too many days for a single destination, advise them
    if raw_days > 10:
        max_feasible = max(1, budget // (600 if people == 1 else 500 * people))
        return {
            "title": f"{city_label} Trip — Duration Advisory",
            "destination": city_label,
            "total_budget": budget,
            "itinerary": [{
                "day": 1, "section": "Trip Too Long for One Destination",
                "activities": [
                    f"You requested {raw_days} days in {city_label} — that's quite ambitious for a single hill station!",
                    f"{city_label} can be thoroughly explored in 3-5 days. Beyond that, you'll run out of new things to do.",
                    f"With your budget of Rs {budget}, you can comfortably do {min(max_feasible, 7)} days.",
                    f"💡 Suggestion: Try a multi-destination trip! For example: '5 days Darjeeling + 3 days Gangtok under {budget} INR'",
                    f"Or try: 'Plan a {min(max_feasible, 5)}-day trip to {city_label} under {budget} INR'"
                ]
            }]
        }

    # ── Budget sanity check ──
    min_budget_per_day = 600 if people == 1 else 500 * people
    min_required = days * min_budget_per_day

    if budget < min_required:
        suggested_days = max(1, budget // min_budget_per_day)
        return {
            "title": f"{city_label} Trip — Budget Advisory",
            "destination": city_label,
            "total_budget": budget,
            "itinerary": [{
                "day": 1, "section": "Budget Too Low",
                "activities": [
                    f"A {days}-day trip to {city_label} for {people} person(s) realistically needs at least Rs {min_required}.",
                    f"Your budget of Rs {budget} works out to Rs {budget // max(days,1)}/day — basic accommodation alone starts at Rs 800-1000/night.",
                    f"💡 Suggestion: Try {suggested_days} day(s) instead, or increase your budget to Rs {min_required}+.",
                    f"Try: 'Plan a {suggested_days}-day trip to {city_label} under {budget} INR'"
                ]
            }]
        }

    # ── Build smart context ──
    context_text = build_smart_context(dest, places, budget, days, preferences)

    # ── Build LLM prompt ──
    pref_str = ", ".join(preferences) if preferences else "general exploration"
    daily_budget = budget // max(days, 1)

    # Build landmark names for prompt reinforcement
    landmark_names = [lm["name"] for lm in REAL_LANDMARKS.get(dest, [])]
    landmark_hint = ", ".join(landmark_names[:6]) if landmark_names else dest_info.get("highlights", "")

    system_prompt = f"""You are 'NB Local', the most knowledgeable AI travel guide for North Bengal & Sikkim.
You speak like a friendly local expert who's lived here for decades.
Output ONLY raw JSON. No markdown, no code fences.

PERSONALITY: Warm, detail-oriented, budget-conscious, culturally aware. Add small local tips and insider knowledge.

STRICT RULES:
1. PRIORITIZE the ★ MUST-VISIT LANDMARKS listed below — these are real, verified places. Use their EXACT names.
2. For accommodation and food, use names from the provided lists. Include price in parentheses.
3. Total spending MUST stay within {budget} INR for {days} days ({people} person(s)).
4. All places must be in {city_label}. Never reference other cities.
5. NEVER invent or hallucinate place names. If you're unsure, use a landmark from the list.
6. Add a brief sensory detail or insider tip to at least 2 activities per day (e.g., "arrive early for mist views", "try the local thukpa here").
7. Vary the activity types each day — mix food, nature, culture, and rest.
8. Consider the time of day: mornings for viewpoints/treks, afternoons for cafes/culture, evenings for markets/dining.

KEY LANDMARKS IN {city_label.upper()} (use these!): {landmark_hint}

ABOUT {city_label.upper()}:
{dest_info.get('tagline', '')} — {dest_info.get('highlights', '')}
Best season: {dest_info.get('best_season', 'Year-round')}
Local tip: {dest_info.get('tip', '')}
Current season: {season_name} — {season_advice}
User preferences: {pref_str}

JSON FORMAT:
{{
  "title": "Creative, evocative trip title mentioning {city_label}",
  "destination": "{city_label}",
  "total_budget": <total estimated spend>,
  "budget_breakdown": {{ "accommodation": <total>, "food": <total>, "activities": <total>, "misc": <total> }},
  "highlights": ["3-4 short highlight phrases for the trip"],
  "itinerary": [
    {{
      "day": 1,
      "section": "Evocative day theme (not just 'Day 1')",
      "activities": [
        "Morning: Description with place name and (price) — add a sensory detail or tip",
        "Afternoon: ...",
        "Evening: ..."
      ]
    }}
  ],
  "pro_tips": ["2-3 practical travel tips specific to this trip"]
}}"""

    user_prompt = f"""Plan my trip: "{prompt}"

{context_text}

{history_context}

Trip details:
- Destination: {city_label}
- Duration: {days} days
- Total budget: {budget} INR ({daily_budget} INR/day)
- Travelers: {people}
- Preferences: {pref_str}
- Season: {season_name}

Create a detailed, day-by-day itinerary. Be specific with timings (morning/afternoon/evening). 
Use ONLY places from the verified list above. Calculate a running total and ensure it stays under {budget} INR."""

    local_resp = None
    try:
        local_resp = call_local_llm([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], temperature=0.35, max_tokens=4000)
    except Exception:
        local_resp = None

    if local_resp:
        try:
            response_text = local_resp["choices"][0]["message"]["content"].strip()
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
            itinerary_data = json.loads(response_text.strip())
            itinerary_data["destination"] = city_label
            itinerary_data.setdefault("title", f"Trip to {city_label}")
            itinerary_data.setdefault("total_budget", budget)
            return itinerary_data
        except Exception as e:
            print(f"Local LLM parse error: {e}")

    client = get_groq_client()
    if not client:
        return _fallback_itinerary(dest, city_label, days, budget, places, preferences)

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.35,
            max_tokens=4000,
        )

        response_text = completion.choices[0].message.content.strip()

        # Clean markdown wrappers
        response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)

        itinerary_data = json.loads(response_text.strip())

        # Enforce consistency
        itinerary_data["destination"] = city_label
        itinerary_data.setdefault("title", f"Trip to {city_label}")
        itinerary_data.setdefault("total_budget", budget)

        return itinerary_data

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}\nRaw response: {response_text[:500]}")
        return _fallback_itinerary(dest, city_label, days, budget, places, preferences)
    except Exception as e:
        print(f"LLM error: {e}")
        return _fallback_itinerary(dest, city_label, days, budget, places, preferences)

# ─── Intelligent Fallback (no LLM needed) ───────────────────────────────────────

def _fallback_itinerary(dest, city_label, days, budget, places, preferences):
    """
    Generate a smart, budget-aware itinerary WITHOUT the LLM.
    Uses real landmarks + deduplicated CSV data for accuracy.
    """
    dest_places = [p for p in places if p["destination"] == dest]
    unique_places = _deduplicate_places(dest_places)
    daily_budget = budget // max(days, 1)
    accom_budget = int(daily_budget * 0.45)
    meal_budget = int(daily_budget * 0.10)  # per meal

    # Get sorted UNIQUE places
    stays = sorted(
        [p for p in unique_places if p["category"] == "accommodation" and extract_price(p.get("price","")) > 0 and extract_price(p.get("price","")) <= accom_budget],
        key=lambda p: -p["rating"]
    )
    meals = sorted(
        [p for p in unique_places if p["category"] == "food_beverage" and extract_price(p.get("price","")) > 0 and extract_price(p.get("price","")) <= meal_budget * 2],
        key=lambda p: -p["rating"]
    )

    if not stays:
        stays = sorted([p for p in unique_places if p["category"] == "accommodation" and extract_price(p.get("price","")) > 0], key=lambda p: extract_price(p.get("price","")))[:3]
    if not meals:
        meals = sorted([p for p in unique_places if p["category"] == "food_beverage" and extract_price(p.get("price","")) > 0], key=lambda p: extract_price(p.get("price","")))[:8]

    # Use REAL LANDMARKS for activities instead of generic CSV names
    landmarks = REAL_LANDMARKS.get(dest, [])
    landmark_activities = [lm for lm in landmarks if lm["type"] not in ("Restaurant", "Cafe")]
    landmark_food = [lm for lm in landmarks if lm["type"] in ("Restaurant", "Cafe")]

    chosen_stay = stays[0] if stays else None
    stay_price = extract_price(chosen_stay.get("price", "")) if chosen_stay else 0
    total_cost = stay_price * days

    itinerary = []
    meal_idx = 0
    lm_idx = 0
    csv_meal_idx = 0

    for d in range(1, days + 1):
        activities = []

        if d == 1 and chosen_stay:
            activities.append(f"Check-in at {chosen_stay['name']} ({chosen_stay.get('price', 'N/A')}/night)")

        # Morning: real landmark
        if lm_idx < len(landmark_activities):
            lm = landmark_activities[lm_idx]
            activities.append(f"Morning: Visit {lm['name']} ({lm['price']}) — {lm['desc']}")
            lm_idx += 1

        # Lunch: prefer landmark food, fall back to CSV
        if meal_idx < len(landmark_food):
            lf = landmark_food[meal_idx]
            activities.append(f"Lunch at {lf['name']} ({lf['price']}) — {lf['desc']}")
            meal_idx += 1
        elif csv_meal_idx < len(meals):
            m = meals[csv_meal_idx]
            activities.append(f"Lunch at {m['name']} ({m.get('price', 'N/A')})")
            total_cost += extract_price(m.get("price", ""))
            csv_meal_idx += 1

        # Afternoon: real landmark
        if lm_idx < len(landmark_activities):
            lm = landmark_activities[lm_idx]
            activities.append(f"Afternoon: Explore {lm['name']} ({lm['price']}) — {lm['desc']}")
            lm_idx += 1

        # Dinner: CSV food
        if csv_meal_idx < len(meals):
            m = meals[csv_meal_idx]
            activities.append(f"Dinner at {m['name']} ({m.get('price', 'N/A')})")
            total_cost += extract_price(m.get("price", ""))
            csv_meal_idx += 1

        if d == days and chosen_stay:
            activities.append(f"Check-out from {chosen_stay['name']}. Departure.")

        themes = ["Arrival & First Impressions", "Deep Exploration", "Culture & Nature", "Hidden Gems",
                   "Adventure Day", "Scenic Trails", "Final Day & Farewell"]
        section = themes[d - 1] if d <= len(themes) else f"Day {d}"

        itinerary.append({"day": d, "section": section, "activities": activities})

    dest_info = DESTINATION_GUIDE.get(dest, {})

    return {
        "title": f"{dest_info.get('tagline', city_label)} — {days}-Day Explorer",
        "destination": city_label,
        "total_budget": min(total_cost, budget),
        "highlights": [dest_info.get("tagline", ""), f"{days} days of exploration", f"Under Rs {budget}"],
        "itinerary": itinerary,
        "pro_tips": [
            dest_info.get("tip", "Carry comfortable walking shoes."),
            f"Best season: {dest_info.get('best_season', 'Oct-March')}",
            "Note: This plan was generated offline. Connect your Groq API key for smarter AI-powered plans."
        ]
    }