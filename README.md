# Ghana Tourism & Hospitality ABSA — Data Pipeline

Data collection + preprocessing pipeline for *Aspect-Based Sentiment Analysis of
Ghanaian Tourist and Hospitality Reviews* (Amoako Benedict Acheampong, 22046313).

Implements proposal Method steps 1–3 (Data Collection, EDA, Preprocessing),
using SerpApi's Tripadvisor Search + Tripadvisor Reviews APIs as the collection
backend.

## Why SerpApi instead of raw scraping

Your proposal's Data Source & Ethics section currently reads *"Manual web
scraping (respecting robots.txt and rate limiting)"*. Worth updating that line
before submission if you go this route: SerpApi is an official, paid,
ToS-compliant API — it doesn't touch Tripadvisor's HTML directly, so
robots.txt/anti-bot concerns are handled on their end rather than yours. It's
arguably a *stronger* ethics story than raw scraping, but it is a different
mechanism than what's currently written down, so the proposal text should
match what you actually did. Your Risks & Fallback Plan already anticipated
anti-scraping blocks and named Google Maps as a fallback — same principle
applies here if you swap data sources.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # then edit .env with your real key
export SERPAPI_API_KEY=your_key_here   # or rely on .env via python-dotenv
```

Sign up for a free SerpApi account (250 searches/month free) at
https://serpapi.com/users/sign_up if you don't have a key yet. Each place
search and each page of reviews counts as one search credit — see "Cost /
quota planning" below before running the full config.

## Running

```bash
# Full pipeline: collect -> anonymize -> EDA
python pipeline.py --steps all

# Or run stages individually (useful across multiple sessions/quota resets)
python pipeline.py --steps collect
python pipeline.py --steps anonymize
python pipeline.py --steps eda
```

Collection is **resumable**: it appends to `data/raw/reviews_raw.jsonl` and
skips `review_id`s it's already seen, so if you hit your monthly quota
partway through, re-running `--steps collect` next month picks up where you
left off instead of re-fetching everything.

## Pipeline stages

| Stage | File | Proposal step | Output |
|---|---|---|---|
| Collect | `scraper.py` | 1. Data Collection | `data/raw/reviews_raw.jsonl`, `data/raw/places_lookup.json` |
| Anonymize | `anonymize.py` | 3. Preprocessing | `data/processed/reviews_clean.csv`, `data/processed/annotation_template.csv` |
| EDA | `eda.py` | 2. EDA | `data/figures/*.png` + printed summary |

Manual aspect annotation (proposal step 4) then happens on
`annotation_template.csv`, which has one row per review with empty
`{aspect}_mentioned` / `{aspect}_sentiment` columns for each of the seven
categories from your Research Questions (accommodation, staff, food,
pricing, cleanliness, safety, cultural_authenticity).

## Ethics safeguards built in

Matching your proposal's Data Source & Ethics section:

- **PII removed during preprocessing**: `anonymize.py` drops `hometown`,
  `display_name`, `avatar`, and profile links entirely; `author_id`/`username`
  are one-way hashed (not stored in plain form) only so QA can check
  one-reviewer-many-reviews patterns without retaining identity.
- **Emails/phone numbers/@mentions inside free-text review bodies** are
  regex-scrubbed as a defensive second layer.
- **All processing done locally**: no review text is sent to any third-party
  AI service in this pipeline — SerpApi only returns Tripadvisor's own public
  review data, it doesn't process or transform the text.
- **<1,000 review cap**: `scraper.run_collection()` stops once the running
  total in `reviews_raw.jsonl` hits 1,000, matching your stated sample size.
- **Rate limiting**: every API call is followed by a randomized 1.5–4s delay,
  with exponential backoff on transient errors (config in `config.py`).

## Cost / quota planning

With the default `config.py` (19 establishments × up to 2 place candidates ×
up to 50 reviews each, in pages of ~10–20 reviews per API call), expect
roughly:
- ~19–38 search credits for place lookups
- ~3–8 credits per establishment for paginated reviews (varies by review volume)

That's comfortably inside the free tier's 250 credits/month if you run it
once; tune `MAX_REVIEWS_PER_PLACE` and `MAX_PLACE_CANDIDATES_PER_QUERY` down
in `config.py` if you want to spread collection across two monthly cycles
instead.

## Customizing targets

Edit `SEARCH_TARGETS` in `config.py` to add/remove establishments. Keep the
category keys (`hotels`, `restaurants`, `attractions`) if you want the
category-level breakdown in `eda.py` to keep working, or add new categories
there — `eda.py` reads categories dynamically from the data, not from a
hardcoded list.
