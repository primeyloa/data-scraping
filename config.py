"""
Configuration for the Ghana Tourism/Hospitality ABSA data pipeline.

Edit SEARCH_TARGETS to change which establishments get scraped.
Everything else (rate limits, output paths, PII patterns) can be tuned
without touching scraper logic.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
load_dotenv()

# ---------------------------------------------------------------------------
# API credentials
# ---------------------------------------------------------------------------
# Never hardcode the key. Set it as an environment variable:
#   export SERPAPI_API_KEY="your_key_here"
# or put it in a .env file (see .env.example) and this will pick it up
# if python-dotenv is installed.
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY", "")


# ---------------------------------------------------------------------------
# Search targets: Ghana tourism & hospitality establishments
# ---------------------------------------------------------------------------
# Grouped by aspect-relevant category so downstream analysis can slice by
# establishment type as well as by aspect (accommodation, staff, food, etc.)
SEARCH_TARGETS = {
    "hotels": [
        "Kempinski Hotel Gold Coast City Accra",
        "Labadi Beach Hotel Accra",
        "Movenpick Ambassador Hotel Accra",
        "Alisa Hotel North Ridge Accra",
        "Royal Senchi Resort Akosombo",
        "Coconut Grove Beach Resort Elmina",
        "Kwahu Cham Cham Hotel",
    ],
    "restaurants": [
        "Chez Afrique Restaurant Accra",
        "Buka Restaurant Osu Accra",
        "Santoku Restaurant Accra",
        "Bistro 22 Accra",
        "Chop Bar Kumasi",
    ],
    "attractions": [
        "Cape Coast Castle",
        "Elmina Castle",
        "Kakum National Park",
        "Kwame Nkrumah Memorial Park Accra",
        "Wli Waterfalls Hohoe",
        "Manhyia Palace Museum Kumasi",
        "Aburi Botanical Gardens",
    ],
}

# Max number of place_id candidates to keep per search query
# (the top result is usually the intended establishment, but ambiguous
# names may need more candidates for manual verification)
MAX_PLACE_CANDIDATES_PER_QUERY = 2

# Max reviews to pull per place. Proposal target is <1,000 reviews TOTAL,
# so this is deliberately conservative across ~19 establishments.
MAX_REVIEWS_PER_PLACE = 50

# ---------------------------------------------------------------------------
# Rate limiting / politeness settings
# ---------------------------------------------------------------------------
# Even though SerpApi is an official API (not raw HTML scraping), we still
# throttle our own request rate: it's good practice, keeps us well under
# API rate limits, and mirrors the "randomized delays" approach described
# in the proposal's Method & Fallback sections.
MIN_DELAY_SECONDS = 1.5
MAX_DELAY_SECONDS = 4.0

# Retry behavior for transient API errors (429, 5xx, network blips)
MAX_RETRIES = 4
BACKOFF_BASE_SECONDS = 2.0  # exponential: base * 2^attempt

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
FIGURES_DIR = BASE_DIR / "data" / "figures"

PLACES_CACHE_FILE = RAW_DIR / "places_lookup.json"
RAW_REVIEWS_FILE = RAW_DIR / "reviews_raw.jsonl"
PROCESSED_REVIEWS_FILE = PROCESSED_DIR / "reviews_clean.csv"
ANNOTATION_TEMPLATE_FILE = PROCESSED_DIR / "annotation_template.csv"

for d in (RAW_DIR, PROCESSED_DIR, FIGURES_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Aspect categories (from proposal's Research Questions)
# ---------------------------------------------------------------------------
ASPECT_CATEGORIES = [
    "accommodation",
    "staff",
    "food",
    "pricing",
    "cleanliness",
    "safety",
    "cultural_authenticity",
]
