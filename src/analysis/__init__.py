"""
Module 3 — Agentic Analysis.

Entry points: analyze_product() runs Agent A (sentiment) + Agent B (pain
points, with the quote guardrail applied) and saves results. compare_products()
runs Agent C (gap analysis) using previously saved pain points for the main
product and its competitors — call analyze_product() for all of them first.
"""

from typing import Dict, List

from src.analysis.agents import AnalysisError, run_gap_analysis, run_pain_point_extraction, run_sentiment_analysis
from src.analysis.guardrail import verify_pain_points
from src.analysis.schemas import GapOpportunityBatch
from src.analysis.storage import get_pain_points, save_gap_opportunities, save_pain_points, save_sentiment_results
from src.ingestion.schema import Review
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

__all__ = ["AnalysisError", "analyze_product", "compare_products"]


def analyze_product(product_id: str, reviews: List[Review]) -> Dict:
    if not reviews:
        raise AnalysisError(f"No reviews available for {product_id} — nothing to analyze.")

    sentiment_batch = run_sentiment_analysis(product_id, reviews)
    save_sentiment_results(product_id, sentiment_batch, reviews)

    pain_point_batch = run_pain_point_extraction(product_id, reviews)
    verified_pain_points = verify_pain_points(pain_point_batch.pain_points, reviews)
    save_pain_points(product_id, verified_pain_points)

    flagged = sum(1 for p in verified_pain_points if p.needs_manual_review)
    if flagged:
        logger.warning(
            "%d/%d pain points for %s flagged for manual review (unverified quotes).",
            flagged, len(verified_pain_points), product_id,
        )

    return {"sentiment": sentiment_batch, "pain_points": verified_pain_points}


def compare_products(main_product_id: str, competitor_product_ids: List[str]) -> GapOpportunityBatch:
    main_pain_points = get_pain_points(main_product_id)
    if not main_pain_points:
        raise AnalysisError(f"No stored pain points for {main_product_id} — run analyze_product() first.")

    competitor_pain_points = {}
    for competitor_id in competitor_product_ids:
        points = get_pain_points(competitor_id)
        if points:
            competitor_pain_points[competitor_id] = points
        else:
            logger.warning("No stored pain points for competitor %s — skipping.", competitor_id)

    gap_batch = run_gap_analysis(main_product_id, main_pain_points, competitor_pain_points)
    save_gap_opportunities(main_product_id, gap_batch)
    return gap_batch
