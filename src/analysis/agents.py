"""
Agents A (sentiment), B (pain points), C (gap comparison) — brief Module 3.

Each review set is batched into a single LLM call per agent per product
(not one call per review) to stay well within Gemini's free-tier rate
limits and the 60-second pipeline budget. Every call is wrapped so a
failure (rate limit, malformed response, network error) raises
AnalysisError with a message safe to show a client, never a raw
stack trace (brief Section 5.2).
"""

from typing import Dict, List

from src.analysis.llm import get_llm
from src.analysis.schemas import (
    GapOpportunityBatch,
    PainPointBatch,
    SentimentBatch,
)
from src.analysis.usage_tracking import log_usage
from src.ingestion.schema import Review
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class AnalysisError(Exception):
    """Raised for any LLM-analysis failure. Callers should show this message, not a stack trace."""


def _format_reviews(reviews: List[Review]) -> str:
    return "\n\n".join(
        f"id: {r.review_id}\nrating: {r.rating}\ntext: {r.review_text}" for r in reviews
    )


def _invoke_structured(prompt: str, schema, agent_name: str, product_id: str):
    llm = get_llm()
    structured_llm = llm.with_structured_output(schema, include_raw=True)
    try:
        response = structured_llm.invoke(prompt)
    except Exception as exc:  # noqa: BLE001 — API/network/rate-limit errors must not crash the app
        logger.error("%s failed for %s: %s", agent_name, product_id, exc)
        raise AnalysisError(f"{agent_name} failed for {product_id}: {exc}") from exc

    parsed = response.get("parsed")
    if parsed is None:
        error = response.get("parsing_error")
        logger.error("%s returned unparseable output for %s: %s", agent_name, product_id, error)
        raise AnalysisError(f"{agent_name} returned output that didn't match the expected format.")

    raw = response.get("raw")
    log_usage(agent_name, product_id, getattr(raw, "usage_metadata", None))
    return parsed


def run_sentiment_analysis(product_id: str, reviews: List[Review]) -> SentimentBatch:
    if not reviews:
        return SentimentBatch(results=[])

    prompt = (
        "Classify the sentiment of each product review below as exactly one of: "
        "Positive, Neutral, or Negative. Base the classification on the review text "
        "(and rating, if given) as a whole.\n\n"
        f"{_format_reviews(reviews)}\n\n"
        "Return one result per review id, covering every id listed above."
    )
    return _invoke_structured(prompt, SentimentBatch, "Agent A (sentiment)", product_id)


def run_pain_point_extraction(product_id: str, reviews: List[Review]) -> PainPointBatch:
    if not reviews:
        return PainPointBatch(pain_points=[])

    prompt = (
        "Below are customer reviews for one product. Identify the top 3 most recurring "
        "customer pain points (complaints), ranked 1-3 by how often they appear.\n\n"
        f"{_format_reviews(reviews)}\n\n"
        "For each pain point, list the review ids that mention it, and copy 1-3 short "
        "supporting quotes VERBATIM from those reviews' text — do not paraphrase the quotes, "
        "copy the exact wording so it can be verified against the source review."
    )
    return _invoke_structured(prompt, PainPointBatch, "Agent B (pain points)", product_id)


def run_gap_analysis(
    main_product_id: str, main_pain_points: List[dict], competitor_pain_points: Dict[str, List[dict]]
) -> GapOpportunityBatch:
    if not competitor_pain_points:
        return GapOpportunityBatch(opportunities=[])

    main_summary = "\n".join(f"- {p['pain_point']}: {p['description']}" for p in main_pain_points) or "(none identified)"
    competitor_summary = "\n\n".join(
        f"Competitor {cid}:\n" + "\n".join(f"- {p['pain_point']}: {p['description']}" for p in points)
        for cid, points in competitor_pain_points.items()
    )

    prompt = (
        "A seller's product has the following known customer pain points:\n"
        f"{main_summary}\n\n"
        "Their competitors have these customer pain points:\n"
        f"{competitor_summary}\n\n"
        "Identify 'Feature Gap Opportunities': competitor pain points that are NOT also "
        "problems for the seller's own product. These are areas the seller could highlight "
        "as an advantage over that competitor. Skip any competitor pain point that closely "
        "matches one of the seller's own pain points."
    )
    return _invoke_structured(prompt, GapOpportunityBatch, "Agent C (gap analysis)", main_product_id)
