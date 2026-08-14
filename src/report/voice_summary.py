"""
Phase 2 Addition 2 (Voice Output) — a short, spoken-friendly summary built
by template from already-computed structured results, not a new LLM call:
every number and fact here is already known, so this is formatting, not
generation — free, instant, deterministic, and nothing new to hallucinate.

Capped to the 3 things the Update Brief says a busy seller most needs to
hear: sentiment split, #1 pain point, #1 recommendation — not everything
already loudly obvious from the dashboard.
"""

from src.analysis import INSUFFICIENT_DATA
from src.report import ComparisonReport


def build_voice_summary(report: ComparisonReport) -> str:
    main = report.main
    total = main.total_reviews

    if total == 0:
        return f"No reviews were available to analyze for {main.product_id}."

    positive_pct = main.sentiment_counts.get("Positive", 0) / total * 100
    negative_pct = main.sentiment_counts.get("Negative", 0) / total * 100

    sentences = [
        f"Here's your quick summary for {main.product_id}, based on {total} reviews. "
        f"{positive_pct:.0f} percent positive, {negative_pct:.0f} percent negative."
    ]

    if main.pain_points:
        top = main.pain_points[0]
        sentences.append(f"Your top customer complaint is {top['pain_point']}.")
        action = top.get("recommended_action")
        if action and action != INSUFFICIENT_DATA:
            sentences.append(f"Recommended action: {action}")
    else:
        sentences.append("No major pain points were identified in this batch of reviews.")

    return " ".join(sentences)
