"""
Optional live review-data API path (brief Section 5.1) — used only when
REVIEW_API_KEY is present in .env. CSV upload remains the default, reliable
path; this is a bonus, not the load-bearing one, so every failure mode here
degrades to APIUnavailableError rather than crashing the run.

Wired for SerpApi's Amazon Reviews API shape (https://serpapi.com/amazon-reviews).
Swap SERPAPI_ENDPOINT / the request params if you use Rainforest API instead —
the response-parsing section is the only part that needs to change.
"""

from typing import List

import requests

from src.ingestion.schema import Review
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

SERPAPI_ENDPOINT = "https://serpapi.com/search"
REQUEST_TIMEOUT_SECONDS = 15
MAX_TARGET_REVIEWS = 300


class APIUnavailableError(Exception):
    """Raised for any live-API failure. Callers should fall back to CSV/sample data, not crash."""


def fetch_reviews_from_api(keyword_or_asin: str, api_key: str) -> List[Review]:
    if not api_key:
        raise APIUnavailableError("No REVIEW_API_KEY configured.")

    params = {
        "engine": "amazon_reviews",
        "asin": keyword_or_asin,
        "api_key": api_key,
    }

    try:
        response = requests.get(SERPAPI_ENDPOINT, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.Timeout as exc:
        raise APIUnavailableError("Review API request timed out.") from exc
    except requests.exceptions.RequestException as exc:
        raise APIUnavailableError(f"Review API request failed: {exc}") from exc

    if response.status_code == 429:
        raise APIUnavailableError("Review API rate limit exceeded.")
    if response.status_code != 200:
        raise APIUnavailableError(f"Review API returned status {response.status_code}.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise APIUnavailableError("Review API returned a non-JSON response.") from exc

    raw_reviews = payload.get("reviews", [])
    if not raw_reviews:
        raise APIUnavailableError("Review API returned no reviews for this product.")

    reviews: List[Review] = []
    for item in raw_reviews[:MAX_TARGET_REVIEWS]:
        text = (item.get("body") or "").strip()
        if not text:
            continue
        # Deliberately not reading item["profile_name"] / item["profile_link"] —
        # reviewer identity is never carried into the Review record (PII handling).
        reviews.append(
            Review(
                product_id=keyword_or_asin,
                review_text=text,
                rating=item.get("rating"),
                review_date=item.get("date"),
                verified_purchase=item.get("verified_purchase"),
                source="api",
            )
        )

    if not reviews:
        raise APIUnavailableError("Review API response contained no usable review text.")

    logger.info("Fetched %d reviews from live API for %s", len(reviews), keyword_or_asin)
    return reviews
