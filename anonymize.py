"""
Preprocessing / anonymization stage (proposal Method step 3 and Ethics section).

Proposal commitment being enforced here:
  "Personal identifiers (names, usernames, locations beyond establishment)
   removed during preprocessing. All processing done locally."

This module:
  1. Drops/hashes reviewer-identifying fields (author_id, username,
     display_name, avatar URL, hometown, profile link).
  2. Regex-scrubs emails, phone numbers, and @mentions that occasionally
     appear inside free-text review snippets or tips.
  3. Normalizes whitespace/encoding for downstream NLP.
  4. Emits a clean, review-text-only dataset plus a separate annotation
     template (review_id + text + empty aspect/sentiment columns) for
     manual labeling.
"""

import hashlib
import json
import re

import pandas as pd

import config

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(\+?\d[\d\-\s()]{7,}\d)")
MENTION_RE = re.compile(r"@\w+")
MULTISPACE_RE = re.compile(r"\s+")


def _hash_id(value: str) -> str:
    """One-way hash so records from the same reviewer can still be linked
    for QA purposes without retaining the actual identifier."""
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def scrub_text(text: str) -> str:
    if not text:
        return ""
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    text = MENTION_RE.sub("[MENTION]", text)
    text = MULTISPACE_RE.sub(" ", text).strip()
    return text


def anonymize_record(raw: dict) -> dict:
    """Map one raw SerpApi review record to a de-identified analysis row."""
    author = raw.get("author", {}) or {}
    trip_info = raw.get("trip_info", {}) or {}

    title = scrub_text(raw.get("title", ""))
    snippet = scrub_text(raw.get("snippet", ""))
    full_text = f"{title}. {snippet}".strip(". ").strip()

    return {
        "review_id": raw.get("review_id"),
        "place_id": raw.get("place_id"),
        "place_name": raw.get("place_name"),
        "category": raw.get("category"),
        "rating": raw.get("rating"),
        "date": raw.get("date"),
        "trip_type": trip_info.get("type"),
        "language": raw.get("language"),
        "text": full_text,
        "text_length": len(full_text),
        "num_votes": raw.get("votes", 0),
        # Reviewer is pseudonymized, never stored in plain form.
        "author_hash": _hash_id(author.get("author_id") or author.get("username", "")),
        "author_contributions": author.get("contributions"),
        # NOTE: hometown/display_name/avatar/profile link intentionally
        # dropped entirely per the proposal's ethics commitment.
    }


def run_anonymization():
    if not config.RAW_REVIEWS_FILE.exists():
        raise FileNotFoundError(
            f"No raw reviews found at {config.RAW_REVIEWS_FILE}. Run scraper.py first."
        )

    rows = []
    seen_ids = set()
    with open(config.RAW_REVIEWS_FILE) as f:
        for line in f:
            raw = json.loads(line)
            rid = raw.get("review_id")
            if rid in seen_ids:
                continue  # de-dupe defensively, in case of overlapping runs
            seen_ids.add(rid)
            rows.append(anonymize_record(raw))

    df = pd.DataFrame(rows)
    # Drop any rows that ended up with empty text after scrubbing
    df = df[df["text"].str.len() > 0].reset_index(drop=True)
    df.to_csv(config.PROCESSED_REVIEWS_FILE, index=False)
    print(f"Wrote {len(df)} de-identified reviews -> {config.PROCESSED_REVIEWS_FILE}")

    # Annotation template: one row per review, empty columns per aspect
    # category for manual labeling (proposal Method step 4).
    ann = df[["review_id", "place_name", "category", "rating", "text"]].copy()
    for aspect in config.ASPECT_CATEGORIES:
        ann[f"{aspect}_mentioned"] = ""   # yes/no
        ann[f"{aspect}_sentiment"] = ""   # positive/negative/neutral
    ann.to_csv(config.ANNOTATION_TEMPLATE_FILE, index=False)
    print(f"Wrote annotation template -> {config.ANNOTATION_TEMPLATE_FILE}")

    return df


if __name__ == "__main__":
    run_anonymization()
