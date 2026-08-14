"""
Module 3 — Agentic Analysis.

Entry points: analyze_product() runs Agent A (sentiment) + Agent B (pain
points, with the quote guardrail applied) + Agent D (recommendations) and
saves results. compare_products() runs Agent C (gap analysis) + Agent D
(recommendations) using previously saved pain points for the main product
and its competitors — call analyze_product() for all of them first.

Agent D (Phase 2 addition) turns each pain point / gap opportunity into
one concrete, actionable line — see CLAUDE.md's Update Brief. A failure
in the recommendation step is logged and swallowed rather than raised:
it's an enhancement on top of the core sentiment/pain-point/gap results,
not something that should take down an otherwise-successful analysis.
"""

from typing import Dict, List

from src.analysis.agents import (
    AnalysisError,
    run_gap_analysis,
    run_gap_recommendations,
    run_pain_point_extraction,
    run_pain_point_recommendations,
    run_sentiment_analysis,
)
from src.analysis.guardrail import verify_pain_points
from src.analysis.schemas import GapOpportunityBatch
from src.analysis.storage import get_pain_points, save_gap_opportunities, save_pain_points, save_sentiment_results
from src.ingestion.schema import Review
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

__all__ = ["AnalysisError", "analyze_product", "compare_products"]

INSUFFICIENT_DATA = "Insufficient data for a specific recommendation."


def analyze_product(product_id: str, reviews: List[Review]) -> Dict:
    if not reviews:
        raise AnalysisError(f"No reviews available for {product_id} — nothing to analyze.")

    sentiment_batch = run_sentiment_analysis(product_id, reviews)
    save_sentiment_results(product_id, sentiment_batch, reviews)

    pain_point_batch = run_pain_point_extraction(product_id, reviews)
    verified_pain_points = verify_pain_points(pain_point_batch.pain_points, reviews)

    try:
        recommendation_batch = run_pain_point_recommendations(product_id, verified_pain_points)
        by_rank = {r.rank: r for r in recommendation_batch.recommendations}
        for point in verified_pain_points:
            rec = by_rank.get(point.rank)
            point.recommended_action = rec.recommended_action if rec else INSUFFICIENT_DATA
            copy = rec.suggested_listing_copy if rec else None
            # A pain point with no groundable recommendation shouldn't show
            # listing copy either — and defensively cap length in case the
            # model doesn't respect the under-200-character instruction.
            if not copy or copy == INSUFFICIENT_DATA or point.recommended_action == INSUFFICIENT_DATA:
                point.suggested_listing_copy = None
            else:
                point.suggested_listing_copy = copy if len(copy) <= 200 else copy[:197].rstrip() + "..."
    except AnalysisError as exc:
        logger.warning("Agent D (recommendations) failed for %s, continuing without them: %s", product_id, exc)

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

    try:
        recommendation_batch = run_gap_recommendations(main_product_id, gap_batch.opportunities)
        by_index = {r.index: r.recommended_action for r in recommendation_batch.recommendations}
        for i, opportunity in enumerate(gap_batch.opportunities, start=1):
            opportunity.recommended_action = by_index.get(i, INSUFFICIENT_DATA)
    except AnalysisError as exc:
        logger.warning(
            "Agent D (recommendations) failed for %s gap opportunities, continuing without them: %s",
            main_product_id, exc,
        )

    save_gap_opportunities(main_product_id, gap_batch)
    return gap_batch
