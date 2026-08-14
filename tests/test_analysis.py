import os

import pytest

from src.analysis.guardrail import verify_pain_points
from src.analysis.schemas import GapOpportunity, GapOpportunityBatch, PainPoint, SentimentBatch, SentimentResult
from src.analysis.storage import (
    get_connection,
    get_gap_opportunities,
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


def test_get_connection_migrates_old_schema_missing_recommended_action(tmp_path):
    # Reproduces the exact bug hit on the deployed app: its SQLite file was
    # created by code that predates the recommended_action column, so a
    # plain CREATE TABLE IF NOT EXISTS is a no-op and the next INSERT
    # column-count-mismatches with sqlite3.OperationalError.
    import sqlite3

    db_path = tmp_path / "old_schema.db"
    old_conn = sqlite3.connect(db_path)
    old_conn.execute(
        """
        CREATE TABLE pain_points (
            product_id TEXT NOT NULL,
            rank INTEGER NOT NULL,
            pain_point TEXT NOT NULL,
            description TEXT NOT NULL,
            supporting_review_ids TEXT NOT NULL,
            supporting_quotes TEXT NOT NULL,
            verified_quote_count INTEGER NOT NULL,
            needs_manual_review INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (product_id, rank)
        )
        """
    )
    old_conn.commit()
    old_conn.close()

    conn = get_connection(str(db_path))
    pain_points = [
        PainPoint(
            rank=1,
            pain_point="Fit",
            description="Ear tips too large",
            supporting_review_ids=["abc123"],
            supporting_quotes=["too large"],
            verified_quote_count=1,
            needs_manual_review=False,
            recommended_action="Add a size chart.",
        )
    ]

    save_pain_points("P1", pain_points, conn=conn)  # must not raise sqlite3.OperationalError
    stored = get_pain_points("P1", conn=conn)

    assert stored[0]["recommended_action"] == "Add a size chart."
    conn.close()


def test_write_time_healing_works_even_if_connection_time_migration_did_not(tmp_path):
    # Isolates _executemany_healing (heals at the point of the actual
    # write, on the exact connection about to fail) from _migrate_schema
    # running at connection-open time, by bypassing get_connection()
    # entirely and opening a raw sqlite3 connection instead — so the
    # connection-open-time migration path never runs at all, and only
    # the write-time healing inside save_pain_points can be responsible
    # for fixing the missing column. This is the safety net for whatever
    # caused the deployed app to still hit the missing-column error even
    # after connection-time migration was added and (per Streamlit
    # Cloud's logs) successfully redeployed.
    import sqlite3

    db_path = tmp_path / "old_schema_no_premigration.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE pain_points (
            product_id TEXT NOT NULL,
            rank INTEGER NOT NULL,
            pain_point TEXT NOT NULL,
            description TEXT NOT NULL,
            supporting_review_ids TEXT NOT NULL,
            supporting_quotes TEXT NOT NULL,
            verified_quote_count INTEGER NOT NULL,
            needs_manual_review INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (product_id, rank)
        )
        """
    )
    conn.commit()

    pain_points = [
        PainPoint(
            rank=1,
            pain_point="Fit",
            description="Ear tips too large",
            supporting_review_ids=["abc123"],
            supporting_quotes=["too large"],
            verified_quote_count=1,
            needs_manual_review=False,
            recommended_action="Add a size chart.",
        )
    ]

    save_pain_points("P1", pain_points, conn=conn)  # must still self-heal and not raise
    stored = get_pain_points("P1", conn=conn)

    assert stored[0]["recommended_action"] == "Add a size chart."
    conn.close()


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
            recommended_action="Add a size chart and an extra-small ear tip to the box.",
        )
    ]
    save_pain_points("P1", pain_points, conn=conn)
    stored = get_pain_points("P1", conn=conn)
    assert len(stored) == 1
    assert stored[0]["pain_point"] == "Fit"
    assert stored[0]["supporting_quotes"] == ["too large"]
    assert stored[0]["recommended_action"] == "Add a size chart and an extra-small ear tip to the box."

    gap_batch = GapOpportunityBatch(
        opportunities=[
            GapOpportunity(
                competitor_product_id="P2",
                competitor_pain_point="Bad mic",
                opportunity="Highlight superior call quality",
                rationale="P1 has no mic complaints",
                recommended_action="Add 'crystal-clear calls' to bullet #2 and the main image.",
            )
        ]
    )
    save_gap_opportunities("P1", gap_batch, conn=conn)
    gap_rows = get_gap_opportunities("P1", conn=conn)
    assert len(gap_rows) == 1
    assert gap_rows[0]["recommended_action"] == "Add 'crystal-clear calls' to bullet #2 and the main image."

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
    # Agent D (recommendations): every pain point should have a non-empty action.
    for point in result["pain_points"]:
        assert point.recommended_action
        assert point.recommended_action.strip() != ""


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="requires a live GEMINI_API_KEY")
def test_compare_products_gap_recommendations_end_to_end(tmp_path, monkeypatch):
    import src.analysis.storage as storage_module

    monkeypatch.setattr(storage_module, "DB_PATH", tmp_path / "live_gap_test.db")

    from src.analysis import analyze_product, compare_products
    from src.ingestion.csv_loader import load_reviews_from_csv
    from tests.test_ingestion import SAMPLE_DIR

    for product_id in ("DEMO-EARBUDS-A", "DEMO-EARBUDS-B"):
        reviews = load_reviews_from_csv(str(SAMPLE_DIR / f"{product_id}.csv"), product_id=product_id)
        analyze_product(product_id, reviews)

    gap_batch = compare_products("DEMO-EARBUDS-A", ["DEMO-EARBUDS-B"])

    assert len(gap_batch.opportunities) > 0
    for opportunity in gap_batch.opportunities:
        assert opportunity.recommended_action
        assert opportunity.recommended_action.strip() != ""
