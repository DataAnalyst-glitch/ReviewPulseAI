"""
CSV upload loader — the default, reliable ingestion path (brief Section 5.1).

Client-supplied review exports vary in column naming, include reviewer PII
we should never store, and often contain empty/duplicate rows. This module
normalizes all of that into a clean, capped list of Review objects and never
raises a raw pandas/stack-trace error to the caller — only CSVLoadError with
a message that's safe to show a client.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.ingestion.schema import Review
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

RAW_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

# Column-name aliases we'll accept for each field (checked case-insensitively).
TEXT_COLUMNS = ["review_text", "review", "text", "body", "review_body", "content"]
RATING_COLUMNS = ["rating", "stars", "star_rating", "score"]
DATE_COLUMNS = ["review_date", "date", "created_at"]
VERIFIED_COLUMNS = ["verified_purchase", "verified"]

# Columns dropped outright if present — reviewer identity is never ingested
# (PII handling, brief Section 5.4).
PII_COLUMNS = [
    "reviewer_name", "author", "author_name", "username", "user_name",
    "user_id", "profile_url", "reviewer_url", "email", "name",
]

MIN_REVIEW_LENGTH = 10
MIN_TARGET_REVIEWS = 30
MAX_TARGET_REVIEWS = 50


class CSVLoadError(Exception):
    """Raised for any CSV problem that should surface as a friendly message, not a stack trace."""


def _find_column(columns_lower: dict, candidates: List[str]) -> Optional[str]:
    for candidate in candidates:
        if candidate in columns_lower:
            return columns_lower[candidate]
    return None


def load_reviews_from_csv(csv_path: str, product_id: str, is_demo_data: bool = False) -> List[Review]:
    path = Path(csv_path)
    if not path.exists():
        raise CSVLoadError(f"File not found: {csv_path}")

    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError as exc:
        raise CSVLoadError("The CSV file is empty.") from exc
    except pd.errors.ParserError as exc:
        raise CSVLoadError("The CSV file is malformed and could not be parsed.") from exc
    except Exception as exc:  # noqa: BLE001 — any other read failure must not crash the app
        raise CSVLoadError(f"Could not read the CSV file: {exc}") from exc

    if df.empty:
        raise CSVLoadError("The CSV file has no rows.")

    columns_lower = {c.strip().lower(): c for c in df.columns}

    text_col = _find_column(columns_lower, TEXT_COLUMNS)
    if text_col is None:
        raise CSVLoadError(
            "No review-text column found. Expected one of: " + ", ".join(TEXT_COLUMNS)
        )

    rating_col = _find_column(columns_lower, RATING_COLUMNS)
    date_col = _find_column(columns_lower, DATE_COLUMNS)
    verified_col = _find_column(columns_lower, VERIFIED_COLUMNS)

    dropped_pii = [columns_lower[c] for c in PII_COLUMNS if c in columns_lower]
    if dropped_pii:
        logger.info("Dropping reviewer-identity columns before ingest: %s", dropped_pii)

    reviews: List[Review] = []
    seen_text = set()

    for _, row in df.iterrows():
        raw_text = row.get(text_col)
        if not isinstance(raw_text, str):
            continue
        text = " ".join(raw_text.split())  # collapse whitespace/newlines
        if len(text) < MIN_REVIEW_LENGTH:
            continue
        if text in seen_text:
            continue
        seen_text.add(text)

        rating = None
        if rating_col is not None:
            try:
                rating = float(row.get(rating_col))
                if pd.isna(rating):
                    rating = None
            except (TypeError, ValueError):
                rating = None

        review_date = None
        if date_col is not None:
            value = row.get(date_col)
            review_date = str(value) if pd.notna(value) else None

        verified = None
        if verified_col is not None:
            value = row.get(verified_col)
            if pd.notna(value):
                verified = str(value).strip().lower() in {"true", "yes", "1", "y"}

        reviews.append(
            Review(
                product_id=product_id,
                review_text=text,
                rating=rating,
                review_date=review_date,
                verified_purchase=verified,
                source="csv",
                is_demo_data=is_demo_data,
            )
        )

    if not reviews:
        raise CSVLoadError("No usable reviews remained after cleaning (all rows empty, too short, or duplicates).")

    if len(reviews) > MAX_TARGET_REVIEWS:
        logger.info("Capping %d cleaned reviews down to %d for %s", len(reviews), MAX_TARGET_REVIEWS, product_id)
        reviews = reviews[:MAX_TARGET_REVIEWS]
    elif len(reviews) < MIN_TARGET_REVIEWS:
        logger.warning(
            "Only %d cleaned reviews for %s (target is %d-%d) — proceeding anyway.",
            len(reviews), product_id, MIN_TARGET_REVIEWS, MAX_TARGET_REVIEWS,
        )

    _save_cleaned_copy(reviews, product_id)
    return reviews


def _save_cleaned_copy(reviews: List[Review], product_id: str) -> Path:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RAW_DATA_DIR / f"{product_id}_{timestamp}.csv"
    pd.DataFrame([r.to_dict() for r in reviews]).to_csv(out_path, index=False)
    logger.info("Saved %d cleaned reviews for %s to %s", len(reviews), product_id, out_path)
    return out_path
