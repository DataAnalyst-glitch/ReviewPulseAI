"""
Module 1 — Data Ingestion.

Entry point: ingest_reviews(). CSV upload is the default, reliable path.
The live API path only runs if REVIEW_API_KEY is set in .env, and any
failure there falls back to CSV / bundled sample data rather than crashing.
"""

import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

from src.ingestion.api_client import APIUnavailableError, fetch_reviews_from_api
from src.ingestion.csv_loader import CSVLoadError, load_reviews_from_csv
from src.ingestion.schema import Review
from src.utils.logging_config import get_logger

load_dotenv()

logger = get_logger(__name__)

SAMPLE_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "sample_reviews"


class IngestionError(Exception):
    """Raised when no review source (CSV, API, or sample data) could be used."""


def ingest_reviews(
    product_id: str,
    csv_path: Optional[str] = None,
    keyword: Optional[str] = None,
) -> List[Review]:
    """
    Resolve reviews for `product_id` using, in order:
      1. An explicitly supplied CSV export (the default, reliable path).
      2. A live API call, only if REVIEW_API_KEY is set in .env.
      3. Bundled demo sample data, clearly logged as a fallback.

    Always returns a list of Review objects or raises IngestionError with a
    user-facing message — never lets a raw stack trace reach the UI layer.
    """
    if csv_path:
        try:
            reviews = load_reviews_from_csv(csv_path, product_id=product_id)
            logger.info("Ingested %d reviews for %s from CSV %s", len(reviews), product_id, csv_path)
            return reviews
        except CSVLoadError as exc:
            logger.error("CSV ingestion failed for %s: %s", product_id, exc)
            raise IngestionError(f"Could not read the uploaded CSV: {exc}") from exc

    api_key = os.getenv("REVIEW_API_KEY", "").strip()
    if api_key:
        try:
            reviews = fetch_reviews_from_api(keyword or product_id, api_key=api_key)
            logger.info("Ingested %d reviews for %s from live API", len(reviews), product_id)
            return reviews
        except APIUnavailableError as exc:
            logger.warning("API ingestion failed for %s, falling back to sample data: %s", product_id, exc)

    sample_path = SAMPLE_DATA_DIR / f"{product_id}.csv"
    if sample_path.exists():
        logger.warning("Using bundled DEMO sample data for %s (no CSV/API provided).", product_id)
        return load_reviews_from_csv(str(sample_path), product_id=product_id, is_demo_data=True)

    raise IngestionError(
        "No review source available: upload a CSV, set REVIEW_API_KEY in .env, "
        f"or add a sample file at data/sample_reviews/{product_id}.csv"
    )
