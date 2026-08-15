import pandas as pd

from src.analysis.stats import (
    MISMATCH_FLAG,
    MISMATCH_HIGH_RATING_NEGATIVE,
    MISMATCH_LOW_RATING_POSITIVE,
    build_comparison_table,
    build_pain_point_timeline,
    find_sentiment_mismatches,
    summarize_timeline_trend,
)


def test_find_sentiment_mismatches_flags_high_rating_negative_and_low_rating_positive():
    rows = [
        {"review_id": "r1", "rating": 5.0, "sentiment": "Negative", "review_text": "Broke after a day but I'm still happy!"},
        {"review_id": "r2", "rating": 1.0, "sentiment": "Positive", "review_text": "Terrible but somehow marked positive"},
        {"review_id": "r3", "rating": 2.0, "sentiment": "Negative", "review_text": "Consistent: low rating, negative sentiment"},
        {"review_id": "r4", "rating": 5.0, "sentiment": "Positive", "review_text": "Consistent: high rating, positive sentiment"},
    ]

    mismatches = find_sentiment_mismatches(rows)

    flagged_ids = {m["review_id"] for m in mismatches}
    assert flagged_ids == {"r1", "r2"}
    for m in mismatches:
        assert m["flag"] == MISMATCH_FLAG
    reasons = {m["review_id"]: m["mismatch_reason"] for m in mismatches}
    assert reasons["r1"] == MISMATCH_HIGH_RATING_NEGATIVE
    assert reasons["r2"] == MISMATCH_LOW_RATING_POSITIVE


def test_find_sentiment_mismatches_ignores_reviews_without_rating():
    rows = [{"review_id": "r1", "rating": None, "sentiment": "Negative", "review_text": "No rating on this one"}]
    assert find_sentiment_mismatches(rows) == []


def test_find_sentiment_mismatches_empty_input():
    assert find_sentiment_mismatches([]) == []


def test_build_comparison_table_computes_per_product_stats():
    review_rows_by_product = {
        "MAIN": [
            {"review_id": "m1", "rating": 5.0, "sentiment": "Positive"},
            {"review_id": "m2", "rating": 1.0, "sentiment": "Negative"},
        ],
        "COMP": [
            {"review_id": "c1", "rating": 3.0, "sentiment": "Neutral"},
        ],
    }

    table = build_comparison_table(review_rows_by_product)

    assert [row["product_id"] for row in table] == ["MAIN", "COMP"]  # main-first order preserved
    main_row = table[0]
    assert main_row["review_count"] == 2
    assert main_row["avg_rating"] == 3.0
    assert main_row["positive_pct"] == 50.0
    assert main_row["negative_pct"] == 50.0
    comp_row = table[1]
    assert comp_row["review_count"] == 1
    assert comp_row["avg_rating"] == 3.0
    assert comp_row["neutral_pct"] == 100.0


def test_build_comparison_table_handles_product_with_no_reviews():
    review_rows_by_product = {"MAIN": [{"review_id": "m1", "rating": 4.0, "sentiment": "Positive"}], "FAILED": []}

    table = build_comparison_table(review_rows_by_product)

    failed_row = next(row for row in table if row["product_id"] == "FAILED")
    assert failed_row["review_count"] == 0
    assert failed_row["avg_rating"] is None


def test_build_comparison_table_empty_input():
    assert build_comparison_table({}) == []


def _pain_points(review_ids_by_point):
    return [{"pain_point": name, "supporting_review_ids": ids} for name, ids in review_ids_by_point.items()]


def test_build_pain_point_timeline_buckets_by_week():
    pain_points = _pain_points({"Battery life": ["r1", "r2"]})
    review_rows = [
        {"review_id": "r1", "review_date": "2026-01-01"},
        {"review_id": "r2", "review_date": "2026-01-25"},  # different week, far enough apart
    ]

    timeline = build_pain_point_timeline(pain_points, review_rows)

    assert not timeline.empty
    assert timeline["pain_point"].unique().tolist() == ["Battery life"]
    assert timeline["count"].sum() == 2
    assert timeline["period"].nunique() == 2


def test_build_pain_point_timeline_returns_empty_with_insufficient_date_coverage():
    # All mentions in the same week -> only 1 distinct period -> not a timeline.
    pain_points = _pain_points({"Battery life": ["r1", "r2"]})
    review_rows = [
        {"review_id": "r1", "review_date": "2026-01-01"},
        {"review_id": "r2", "review_date": "2026-01-02"},
    ]

    timeline = build_pain_point_timeline(pain_points, review_rows)

    assert timeline.empty


def test_build_pain_point_timeline_handles_missing_dates():
    pain_points = _pain_points({"Battery life": ["r1", "r2"]})
    review_rows = [{"review_id": "r1", "review_date": None}, {"review_id": "r2", "review_date": ""}]

    timeline = build_pain_point_timeline(pain_points, review_rows)

    assert timeline.empty


def test_build_pain_point_timeline_empty_input():
    assert build_pain_point_timeline([], []).empty
    assert build_pain_point_timeline([{"pain_point": "X", "supporting_review_ids": ["r1"]}], []).empty


def test_summarize_timeline_trend_labels_increasing_and_decreasing():
    timeline = pd.DataFrame(
        [
            {"period": pd.Timestamp("2026-01-01"), "pain_point": "Rising issue", "count": 1},
            {"period": pd.Timestamp("2026-02-01"), "pain_point": "Rising issue", "count": 5},
            {"period": pd.Timestamp("2026-01-01"), "pain_point": "Fading issue", "count": 5},
            {"period": pd.Timestamp("2026-02-01"), "pain_point": "Fading issue", "count": 1},
        ]
    )

    trend = summarize_timeline_trend(timeline)
    by_point = {row["pain_point"]: row for row in trend}

    assert by_point["Rising issue"]["trend"] == "increasing"
    assert by_point["Fading issue"]["trend"] == "decreasing"


def test_summarize_timeline_trend_empty_input():
    assert summarize_timeline_trend(pd.DataFrame(columns=["period", "pain_point", "count"])) == []
