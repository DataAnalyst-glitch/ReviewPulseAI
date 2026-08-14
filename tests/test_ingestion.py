from pathlib import Path

import pandas as pd
import pytest

from src.ingestion import IngestionError, ingest_reviews
from src.ingestion.csv_loader import CSVLoadError, load_reviews_from_csv

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample_reviews"


def test_load_reviews_from_csv_cleans_and_strips_pii():
    reviews = load_reviews_from_csv(str(SAMPLE_DIR / "DEMO-EARBUDS-A.csv"), product_id="DEMO-EARBUDS-A")

    assert len(reviews) >= 10
    for review in reviews:
        assert review.review_text.strip() != ""
        assert len(review.review_text) >= 10
        assert not hasattr(review, "reviewer_name")
        assert not hasattr(review, "profile_url")

    texts = [r.review_text for r in reviews]
    assert len(texts) == len(set(texts))  # duplicates removed


def test_load_reviews_from_csv_missing_file_raises_friendly_error():
    with pytest.raises(CSVLoadError):
        load_reviews_from_csv("does_not_exist.csv", product_id="X")


def test_load_reviews_from_csv_missing_text_column_raises_friendly_error(tmp_path):
    bad_csv = tmp_path / "bad.csv"
    pd.DataFrame({"rating": [5, 4]}).to_csv(bad_csv, index=False)

    with pytest.raises(CSVLoadError):
        load_reviews_from_csv(str(bad_csv), product_id="X")


def test_ingest_reviews_uses_explicit_csv_path():
    reviews = ingest_reviews("DEMO-EARBUDS-A", csv_path=str(SAMPLE_DIR / "DEMO-EARBUDS-A.csv"))
    assert len(reviews) >= 10


def test_ingest_reviews_falls_back_to_bundled_sample_data(monkeypatch):
    monkeypatch.delenv("REVIEW_API_KEY", raising=False)
    reviews = ingest_reviews("DEMO-EARBUDS-B")
    assert len(reviews) >= 10
    assert all(r.is_demo_data for r in reviews)


def test_ingest_reviews_raises_when_nothing_available(monkeypatch):
    monkeypatch.delenv("REVIEW_API_KEY", raising=False)
    with pytest.raises(IngestionError):
        ingest_reviews("NO-SUCH-PRODUCT")
