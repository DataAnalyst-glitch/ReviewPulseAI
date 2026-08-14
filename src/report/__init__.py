"""
Module 4 report data — a read-only view over Module 3's stored results.
Deliberately has no LLM/ingestion dependency: building a report is just
reading what analyze_product()/compare_products() already saved, so the
Streamlit UI and the PDF generator can both call this without re-running
analysis.
"""

from dataclasses import dataclass
from typing import Dict, List

from src.analysis.storage import get_gap_opportunities, get_pain_points, get_product_sentiment


@dataclass
class ProductReport:
    product_id: str
    is_demo_data: bool
    total_reviews: int
    sentiment_counts: Dict[str, int]
    pain_points: List[dict]


@dataclass
class ComparisonReport:
    main: ProductReport
    competitors: List[ProductReport]
    gap_opportunities: List[dict]


def build_product_report(product_id: str) -> ProductReport:
    sentiment = get_product_sentiment(product_id)
    pain_points = get_pain_points(product_id)
    return ProductReport(
        product_id=product_id,
        is_demo_data=sentiment["is_demo_data"],
        total_reviews=sentiment["total"],
        sentiment_counts=sentiment["counts"],
        pain_points=pain_points,
    )


def build_comparison_report(main_product_id: str, competitor_ids: List[str]) -> ComparisonReport:
    main = build_product_report(main_product_id)
    competitors = [build_product_report(cid) for cid in competitor_ids]
    gaps = get_gap_opportunities(main_product_id)
    return ComparisonReport(main=main, competitors=competitors, gap_opportunities=gaps)
