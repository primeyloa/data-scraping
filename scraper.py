"""
Data collection stage (proposal Method step 1).

Two-phase collection, mirroring SerpApi's Tripadvisor engines:
  1. search_places()  -> engine=tripadvisor        (name -> place_id)
  2. fetch_reviews()  -> engine=tripadvisor_reviews (place_id -> reviews, paginated)

Design goals:
  - Resumable: raw reviews are appended to a JSONL file as they arrive, and
    already-collected review_ids are skipped on re-run, so a crash or a
    hit API quota doesn't lose progress.
  - Polite: randomized delay between every API call, exponential backoff
    on transient errors, and a hard cap on reviews per place.
  - Traceable: every raw record keeps its source place_id/place_name so
    later stages can slice by establishment or category.
"""

import json
import logging
import random
import time
from typing import Optional

import serpapi

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("scraper")


def _client() -> "serpapi.Client":
    if not config.SERPAPI_API_KEY:
        raise RuntimeError(
            "SERPAPI_API_KEY is not set. Export it as an environment variable "
            "or add it to a .env file before running the pipeline."
        )
    return serpapi.Client(api_key=config.SERPAPI_API_KEY)


def _polite_sleep():
    time.sleep(random.uniform(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS))


def _call_with_retries(fn, **params):
    """Call a SerpApi search with exponential backoff on failure."""
    last_err = None
    for attempt in range(config.MAX_RETRIES):
        try:
            return fn(**params)
        except Exception as e:  # SerpApi client raises on HTTP/API errors
            last_err = e
            wait = config.BACKOFF_BASE_SECONDS * (2 ** attempt)
            log.warning(
                "API call failed (attempt %d/%d): %s — retrying in %.1fs",
                attempt + 1, config.MAX_RETRIES, e, wait,
            )
            time.sleep(wait)
    raise RuntimeError(f"API call failed after {config.MAX_RETRIES} attempts") from last_err


# ---------------------------------------------------------------------------
# Phase 1: resolve establishment names -> place_id
# ---------------------------------------------------------------------------

def search_places(query: str, client: Optional["serpapi.Client"] = None) -> list[dict]:
    """Search Tripadvisor for a place name, return candidate place records."""
    client = client or _client()
    log.info("Searching for place: %s", query)

    raw_results = _call_with_retries(
        client.search,
        engine="tripadvisor",
        q=query,
    )
    
    # Safely convert the SerpResults object to a standard Python dictionary
    results = raw_results.as_dict() if hasattr(raw_results, "as_dict") else dict(raw_results)

    candidates = []
    
    # FIX: Tripadvisor returns establishments under "places" or "locations", NOT "organic_results"
    search_results = results.get("places") or results.get("locations") or []
    
    for item in search_results[: config.MAX_PLACE_CANDIDATES_PER_QUERY]:
        # FIX: The ID is definitely called 'place_id'
        place_id = item.get("place_id")
        
        if not place_id:
            continue
            
        candidates.append(
            {
                "query": query,
                "place_id": str(place_id),
                "name": item.get("title") or item.get("name"),
                "type": item.get("type"),
                "rating": item.get("rating"),
            }
        )
        
    if not candidates:
        log.warning("No place_id found for query: %s", query)
    _polite_sleep()
    return candidates


def build_places_lookup() -> list[dict]:
    """Resolve every SEARCH_TARGETS entry into place_id candidates, with caching."""
    if config.PLACES_CACHE_FILE.exists():
        log.info("Loading cached places lookup from %s", config.PLACES_CACHE_FILE)
        with open(config.PLACES_CACHE_FILE) as f:
            return json.load(f)

    client = _client()
    all_places = []
    for category, queries in config.SEARCH_TARGETS.items():
        for q in queries:
            for place in search_places(q, client=client):
                place["category"] = category
                all_places.append(place)

    with open(config.PLACES_CACHE_FILE, "w") as f:
        json.dump(all_places, f, indent=2)
    log.info("Resolved %d place candidates -> %s", len(all_places), config.PLACES_CACHE_FILE)
    return all_places


# ---------------------------------------------------------------------------
# Phase 2: paginated review collection
# ---------------------------------------------------------------------------

def _load_seen_review_ids() -> set[str]:
    seen = set()
    if config.RAW_REVIEWS_FILE.exists():
        with open(config.RAW_REVIEWS_FILE) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    seen.add(rec.get("review_id"))
                except json.JSONDecodeError:
                    continue
    return seen


def fetch_reviews_for_place(
    place: dict, client: Optional["serpapi.Client"] = None, seen_ids: Optional[set] = None
) -> int:
    """Fetch up to MAX_REVIEWS_PER_PLACE reviews for one place_id, paginating.

    Appends new reviews to RAW_REVIEWS_FILE as JSONL. Returns count of new
    reviews written for this place.
    """
    client = client or _client()
    seen_ids = seen_ids if seen_ids is not None else _load_seen_review_ids()
    place_id = place["place_id"]

    collected = 0
    params = {"engine": "tripadvisor_reviews", "place_id": place_id}

    with open(config.RAW_REVIEWS_FILE, "a") as out_f:
        next_page_params = params
        while collected < config.MAX_REVIEWS_PER_PLACE and next_page_params:
            results = _call_with_retries(client.search, **next_page_params)
            reviews = results.get("reviews", [])
            if not reviews:
                log.info("No more reviews for place_id=%s (%s)", place_id, place.get("name"))
                break

            for review in reviews:
                if collected >= config.MAX_REVIEWS_PER_PLACE:
                    break
                review_id = review.get("review_id")
                if review_id in seen_ids:
                    continue  # already collected in a previous run
                record = {
                    **review,
                    "place_id": place_id,
                    "place_name": place.get("name"),
                    "category": place.get("category"),
                }
                out_f.write(json.dumps(record) + "\n")
                out_f.flush()
                seen_ids.add(review_id)
                collected += 1

            _polite_sleep()

            # SerpApi pagination: follow serpapi_pagination.next if present
            pagination = results.get("serpapi_pagination", {})
            next_url = pagination.get("next")
            if next_url and collected < config.MAX_REVIEWS_PER_PLACE:
                next_page_params = {"engine": "tripadvisor_reviews", "data_id": place_id}
                # SerpApi Python client can follow a raw search URL directly;
                # simplest robust approach is to re-request with a page token
                # if the API exposes one, otherwise stop (avoids fragile URL
                # parsing across client library versions).
                offset = pagination.get("next_page_token") or pagination.get("next_offset")
                if offset:
                    next_page_params["offset"] = offset
                else:
                    next_page_params = None
            else:
                next_page_params = None

    log.info("Collected %d new reviews for %s (place_id=%s)", collected, place.get("name"), place_id)
    return collected


def run_collection():
    """Full Phase 1 + Phase 2 collection run, respecting the <1,000 review cap."""
    places = build_places_lookup()
    seen_ids = _load_seen_review_ids()
    total_so_far = len(seen_ids)
    log.info("Starting from %d already-collected reviews", total_so_far)

    client = _client()
    for place in places:
        if total_so_far >= 1000:
            log.info("Reached proposal's 1,000-review cap. Stopping collection.")
            break
        new_count = fetch_reviews_for_place(place, client=client, seen_ids=seen_ids)
        total_so_far += new_count

    log.info("Collection complete. Total reviews in %s: %d", config.RAW_REVIEWS_FILE, total_so_far)


if __name__ == "__main__":
    run_collection()
