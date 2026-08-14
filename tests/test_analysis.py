import os

import pytest

from src.analysis.guardrail import verify_pain_points
from src.analysis.schemas import GapOpportunity, GapOpportunityBatch, PainPoint, SentimentBatch, SentimentResult
from src.analysis.storage import (
    get_connection,
    get_pain_points,
    log_llm_usage,
    save_gap_opportunities,
    save_pain_points,
    save_sentiment_results,
)
from src.ingestion.schema import Review


def _review(product_id: str, text: str, rating: float = 4.0) -> Review:
    return Review(product_id=product_id, review_text=text, rating=rating)


def test_verify_pain_points_flags_unverifiable_quotes():
    reviews = [_review("P1", "The battery drains extremely fast, dead by noon.")]
    pain_points = [
        PainPoint(
            rank=1,
            pain_point="Battery life",
            description="Battery drains quickly",
            supporting_review_ids=[reviews[0].review_id],
            supporting_quotes=["battery drains extremely fast"],
        ),
        PainPoint(
            rank=2,
            pain_point="Made up issue",
            description="Something not actually in the source review",
            supporting_review_ids=[reviews[0].review_id],
            supporting_quotes=["catches fire when charging"],
        ),
    ]

    verified = verify_pain_points(pain_points, reviews)

    assert verified[0].verified_quote_count == 1
    assert verified[0].needs_manual_review is False
    assert verified[1].verified_quote_count == 0
    assert verified[1].needs_manual_review is True


def test_storage_round_trip(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))

    reviews = [_review("P1", "Great sound quality overall.")]
    sentiment_batch = SentimentBatch(results=[SentimentResult(review_id=reviews[0].review_id, sentiment="Positive")])
    save_sentiment_results("P1", sentiment_batch, reviews, conn=conn)
    assert conn.execute("SELECT COUNT(*) FROM sentiment_results").fetchone()[0] == 1

    pain_points = [
        PainPoint(
            rank=1,
            pain_point="Fit",
            description="Ear tips too large",
            supporting_review_ids=[reviews[0].review_id],
            supporting_quotes=["too large"],
            verified_quote_count=1,
            needs_manual_review=False,
        )
    ]
    save_pain_points("P1", pain_points, conn=conn)
    stored = get_pain_points("P1", conn=conn)
    assert len(stored) == 1
    assert stored[0]["pain_point"] == "Fit"
    assert stored[0]["supporting_quotes"] == ["too large"]

    gap_batch = GapOpportunityBatch(
        opportunities=[
            GapOpportunity(
                competitor_product_id="P2",
                competitor_pain_point="Bad mic",
                opportunity="Highlight superior call quality",
                rationale="P1 has no mic complaints",
            )
        ]
    )
    save_gap_opportunities("P1", gap_batch, conn=conn)
    assert conn.execute("SELECT COUNT(*) FROM gap_opportunities WHERE main_product_id = 'P1'").fetchone()[0] == 1

    log_llm_usage("Agent A", "P1", "gemini-2.5-flash", 100, 50, 150, conn=conn)
    assert conn.execute("SELECT COUNT(*) FROM llm_usage_log").fetchone()[0] == 1

    conn.close()


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="requires a live GEMINI_API_KEY")
def test_analyze_product_end_to_end(tmp_path, monkeypatch):
    import src.analysis.storage as storage_module

    monkeypatch.setattr(storage_module, "DB_PATH", tmp_path / "live_test.db")

    from src.analysis import analyze_product
    from src.ingestion.csv_loader import load_reviews_from_csv
    from tests.test_ingestion import SAMPLE_DIR

    reviews = load_reviews_from_csv(str(SAMPLE_DIR / "DEMO-EARBUDS-A.csv"), product_id="DEMO-EARBUDS-A")
    result = analyze_product("DEMO-EARBUDS-A", reviews)

    assert len(result["sentiment"].results) == len(reviews)
    assert 0 < len(result["pain_points"]) <= 3
