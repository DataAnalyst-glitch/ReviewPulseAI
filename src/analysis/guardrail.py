"""
Pain-point quote guardrail (brief Section 5.4) — a lightweight, automated
check that supplements, not replaces, the "spot-check 5-10 outputs
manually before showing any client demo" step the brief also calls for.

For each supporting quote the pain-point agent produced, confirm it's an
actual quote or close paraphrase of the source review it's attributed to,
rather than something the model invented. Flags anything that fails so
manual spot-checking can focus there first.
"""

import difflib
import re
from typing import List

from src.analysis.schemas import PainPoint
from src.ingestion.schema import Review
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

FUZZY_MATCH_THRESHOLD = 0.6


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _quote_matches_text(quote: str, text: str) -> bool:
    quote_norm = _normalize(quote)
    text_norm = _normalize(text)
    if not quote_norm:
        return False
    if quote_norm in text_norm:
        return True
    return difflib.SequenceMatcher(None, quote_norm, text_norm).ratio() >= FUZZY_MATCH_THRESHOLD


def verify_pain_points(pain_points: List[PainPoint], reviews: List[Review]) -> List[PainPoint]:
    reviews_by_id = {r.review_id: r.review_text for r in reviews}

    for pain_point in pain_points:
        verified = 0
        for quote in pain_point.supporting_quotes:
            candidate_texts = [
                reviews_by_id[rid] for rid in pain_point.supporting_review_ids if rid in reviews_by_id
            ]
            if any(_quote_matches_text(quote, text) for text in candidate_texts):
                verified += 1

        pain_point.verified_quote_count = verified
        pain_point.needs_manual_review = verified == 0

        if pain_point.needs_manual_review:
            logger.warning(
                "Pain point '%s' has no verifiable supporting quotes — flagged for manual review.",
                pain_point.pain_point,
            )

    return pain_points
