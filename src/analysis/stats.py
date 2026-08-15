"""
Pandas-based statistical layer — a lightweight complement to the LLM
analysis, not a replacement. Nothing in this module calls an LLM: every
number here is derived directly from stored ratings/sentiment/dates via
pandas, so it's free, deterministic, and a genuinely independent signal
alongside the AI-generated pain points, recommendations, and gap
opportunities. Callers (src/report) are responsible for labeling these
results as "statistical" / "rating-based" wherever they're shown, so a
reader can always tell which claim came from which method.
"""

from typing import Dict, List

import pandas as pd

MISMATCH_FLAG = "Sentiment mismatch - needs review"
MISMATCH_HIGH_RATING_NEGATIVE = "4-5 star rating classified as Negative"
MISMATCH_LOW_RATING_POSITIVE = "1-2 star rating classified as Positive"

TIMELINE_FREQ = "W"  # weekly buckets


def find_sentiment_mismatches(review_rows: List[Dict]) -> List[Dict]:
    """
    Cross-checks each review's star rating against the LLM's sentiment
    label (Agent A) — a second, independent accuracy guardrail alongside
    the quote-verification check in guardrail.py. That one checks whether
    Agent B's pain-point quotes actually appear in the source review text;
    this one checks whether Agent A's sentiment call agrees with the
    reviewer's own star rating. Flags:
      - 4-5 stars classified as Negative
      - 1-2 stars classified as Positive
    Reviews with no rating are skipped — there's nothing to cross-check.
    """
    if not review_rows:
        return []

    df = pd.DataFrame(review_rows)
    if "rating" not in df.columns or "sentiment" not in df.columns:
        return []
    df = df.dropna(subset=["rating"])
    if df.empty:
        return []

    high_rating_negative = (df["rating"] >= 4) & (df["sentiment"] == "Negative")
    low_rating_positive = (df["rating"] <= 2) & (df["sentiment"] == "Positive")
    mismatched = df[high_rating_negative | low_rating_positive].copy()
    if mismatched.empty:
        return []

    mismatched["mismatch_reason"] = mismatched["rating"].apply(
        lambda r: MISMATCH_HIGH_RATING_NEGATIVE if r >= 4 else MISMATCH_LOW_RATING_POSITIVE
    )
    mismatched = mismatched.sort_values("rating", ascending=False)

    return [
        {
            "review_id": row["review_id"],
            "rating": row["rating"],
            "sentiment": row["sentiment"],
            "review_text": row["review_text"],
            "flag": MISMATCH_FLAG,
            "mismatch_reason": row["mismatch_reason"],
        }
        for _, row in mismatched.iterrows()
    ]


def build_comparison_table(review_rows_by_product: Dict[str, List[Dict]]) -> List[Dict]:
    """
    Plain statistical comparison (pandas groupby, no LLM call) — average
    rating, review count, and sentiment ratio side by side for the main
    product vs each competitor. Distinct from (and a complement to) the
    AI-generated Feature Gap Opportunities: this is "hard numbers"
    evidence, not an interpreted claim. Product order in the output
    matches the input dict's key order (main product first).
    """
    if not review_rows_by_product:
        return []

    frames = []
    for product_id, rows in review_rows_by_product.items():
        df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["review_id", "sentiment", "rating"])
        df["product_id"] = product_id
        frames.append(df)
    all_reviews = pd.concat(frames, ignore_index=True)

    review_count = all_reviews.groupby("product_id").size()
    avg_rating = all_reviews.groupby("product_id")["rating"].mean().round(2)

    sentiment_counts = (
        all_reviews.dropna(subset=["sentiment"]).groupby(["product_id", "sentiment"]).size().unstack(fill_value=0)
    )
    for col in ("Positive", "Neutral", "Negative"):
        if col not in sentiment_counts.columns:
            sentiment_counts[col] = 0
    sentiment_pct = sentiment_counts.div(sentiment_counts.sum(axis=1), axis=0).mul(100).round(1)

    table = pd.DataFrame({"review_count": review_count, "avg_rating": avg_rating})
    table = table.join(sentiment_pct[["Positive", "Neutral", "Negative"]])
    table = table.reindex(review_rows_by_product.keys())  # preserve main-first order, keep all-zero products
    table = table.rename(columns={"Positive": "positive_pct", "Neutral": "neutral_pct", "Negative": "negative_pct"})
    table = table.reset_index().rename(columns={"index": "product_id"})

    records = table.to_dict("records")
    for record in records:
        if pd.isna(record.get("avg_rating")):
            record["avg_rating"] = None
        for key in ("positive_pct", "neutral_pct", "negative_pct", "review_count"):
            if pd.isna(record.get(key)):
                record[key] = 0
        record["review_count"] = int(record["review_count"])
    return records


def build_pain_point_timeline(pain_points: List[Dict], review_rows: List[Dict]) -> pd.DataFrame:
    """
    Pain-point mention frequency over time (pandas-based, no LLM) — a proxy
    signal for when an issue may be affecting sales, since exact sales or
    demographic data isn't accessible from reviews alone. Buckets each pain
    point's supporting reviews by review_date at weekly resolution. Reviews
    with a missing/unparseable date are excluded from the timeline (there's
    nothing to bucket them into) but don't block the rest of the report -
    this is a best-effort proxy signal, not a hard requirement. Returns an
    empty DataFrame if there isn't enough date coverage to say anything
    meaningful (fewer than 2 distinct periods with data).
    """
    empty = pd.DataFrame(columns=["period", "pain_point", "count"])
    if not pain_points or not review_rows:
        return empty

    date_by_review_id = {row["review_id"]: row.get("review_date") for row in review_rows if row.get("review_date")}

    records = []
    for point in pain_points:
        for review_id in point.get("supporting_review_ids", []):
            raw_date = date_by_review_id.get(review_id)
            if not raw_date:
                continue
            records.append({"pain_point": point["pain_point"], "review_date": raw_date})

    if not records:
        return empty

    df = pd.DataFrame(records)
    df["review_date"] = pd.to_datetime(df["review_date"], errors="coerce")
    df = df.dropna(subset=["review_date"])
    if df.empty:
        return empty

    df["period"] = df["review_date"].dt.to_period(TIMELINE_FREQ).dt.start_time
    timeline = df.groupby(["period", "pain_point"]).size().reset_index(name="count")

    if timeline["period"].nunique() < 2:
        return empty

    return timeline.sort_values("period").reset_index(drop=True)


def summarize_timeline_trend(timeline: pd.DataFrame) -> List[Dict]:
    """
    Collapses the weekly timeline into a simple earlier-half vs later-half
    comparison per pain point - compact enough for the PDF's text-only
    layout (which deliberately doesn't embed chart images), while the
    Streamlit UI shows the full chart built from the same timeline data.
    """
    if timeline is None or timeline.empty:
        return []

    periods = sorted(timeline["period"].unique())
    midpoint = max(len(periods) // 2, 1)
    earlier_periods = set(periods[:midpoint])

    results = []
    for pain_point, group in timeline.groupby("pain_point"):
        earlier = int(group[group["period"].isin(earlier_periods)]["count"].sum())
        later = int(group[~group["period"].isin(earlier_periods)]["count"].sum())
        if earlier == 0 and later > 0:
            trend = "new/rising"
        elif later > earlier:
            trend = "increasing"
        elif later < earlier:
            trend = "decreasing"
        else:
            trend = "steady"
        results.append({"pain_point": pain_point, "earlier_count": earlier, "later_count": later, "trend": trend})
    return results
