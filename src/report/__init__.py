"""
Module 4 report data — a read-only view over Module 3's stored results.
Deliberately has no LLM/ingestion dependency: building a report is just
reading what analyze_product()/compare_products() already saved, so the
Streamlit UI and the PDF generator can both call this without re-running
analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.analysis.stats import build_comparison_table, build_pain_point_timeline, find_sentiment_mismatches, summarize_timeline_trend
from src.analysis.storage import get_gap_opportunities, get_pain_points, get_product_sentiment, get_sentiment_details


@dataclass
class ProductReport:
    product_id: str
    is_demo_data: bool
    total_reviews: int
    sentiment_counts: Dict[str, int]
    pain_points: List[dict]
    # Statistical layer (src/analysis/stats.py) - pandas-based, no LLM call.
    # A complement to the AI analysis above, not a replacement - kept as
    # separate fields so callers can label them distinctly.
    has_rating_data: bool = False
    avg_rating: Optional[float] = None
    sentiment_mismatches: List[dict] = field(default_factory=list)
    pain_point_timeline: List[dict] = field(default_factory=list)  # [{period, pain_point, count}]
    pain_point_trend: List[dict] = field(default_factory=list)  # [{pain_point, earlier_count, later_count, trend}]


@dataclass
class ComparisonReport:
    main: ProductReport
    competitors: List[ProductReport]
    gap_opportunities: List[dict]
    # Statistical comparison (pandas groupby) - "hard numbers" alongside the
    # AI-generated gap_opportunities above, not a replacement for them.
    comparison_table: List[dict] = field(default_factory=list)


def disclaimer_text(review_count: int) -> str:
    """
    Trust/accuracy disclaimer shown on both the Streamlit results page and
    the PDF footer — one source of wording so the two surfaces can't drift.
    Short and professional, not alarming: sets accurate expectations about
    what this analysis is (and isn't) without undermining confidence in it.
    """
    return (
        f"This analysis is based on customer review text only ({review_count} reviews analyzed) "
        "and does not incorporate sales volume, pricing, or market trend data. "
        "Use alongside your own business judgment and other data sources."
    )


def build_product_report(product_id: str) -> ProductReport:
    sentiment = get_product_sentiment(product_id)
    pain_points = get_pain_points(product_id)
    review_rows = get_sentiment_details(product_id)

    ratings = [row["rating"] for row in review_rows if row.get("rating") is not None]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

    timeline_df = build_pain_point_timeline(pain_points, review_rows)
    pain_point_timeline = [
        {"period": period.date().isoformat(), "pain_point": pain_point, "count": int(count)}
        for period, pain_point, count in timeline_df.itertuples(index=False)
    ]

    return ProductReport(
        product_id=product_id,
        is_demo_data=sentiment["is_demo_data"],
        total_reviews=sentiment["total"],
        sentiment_counts=sentiment["counts"],
        pain_points=pain_points,
        has_rating_data=bool(ratings),
        avg_rating=avg_rating,
        sentiment_mismatches=find_sentiment_mismatches(review_rows),
        pain_point_timeline=pain_point_timeline,
        pain_point_trend=summarize_timeline_trend(timeline_df),
    )


def build_comparison_report(main_product_id: str, competitor_ids: List[str]) -> ComparisonReport:
    main = build_product_report(main_product_id)
    competitors = [build_product_report(cid) for cid in competitor_ids]
    gaps = get_gap_opportunities(main_product_id)

    review_rows_by_product = {
        report.product_id: get_sentiment_details(report.product_id) for report in [main] + competitors
    }
    comparison_table = build_comparison_table(review_rows_by_product)

    return ComparisonReport(main=main, competitors=competitors, gap_opportunities=gaps, comparison_table=comparison_table)
