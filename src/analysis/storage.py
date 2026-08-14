"""
Local SQLite persistence for Module 3 results — a drop-in stand-in for
"save all structured results back to Supabase" until Supabase is set up.
Using SQL here (not JSON files) so the eventual migration to Supabase
Postgres is a schema port, not a data-model rewrite.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from src.analysis.schemas import GapOpportunityBatch, PainPoint, SentimentBatch
from src.ingestion.schema import Review
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "reviewpulse.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sentiment_results (
    review_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    rating REAL,
    review_text TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pain_points (
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
);

CREATE TABLE IF NOT EXISTS gap_opportunities (
    main_product_id TEXT NOT NULL,
    competitor_product_id TEXT NOT NULL,
    competitor_pain_point TEXT NOT NULL,
    opportunity TEXT NOT NULL,
    rationale TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    agent TEXT NOT NULL,
    product_id TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER
);
"""


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_sentiment_results(
    product_id: str, sentiment_batch: SentimentBatch, reviews: List[Review], conn: Optional[sqlite3.Connection] = None
) -> None:
    own_conn = conn is None
    conn = conn or get_connection()
    reviews_by_id = {r.review_id: r for r in reviews}
    now = _now()

    rows = []
    for result in sentiment_batch.results:
        review = reviews_by_id.get(result.review_id)
        if review is None:
            continue
        rows.append((result.review_id, product_id, result.sentiment, review.rating, review.review_text, now))

    conn.executemany(
        "INSERT OR REPLACE INTO sentiment_results "
        "(review_id, product_id, sentiment, rating, review_text, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    logger.info("Saved %d sentiment results for %s", len(rows), product_id)
    if own_conn:
        conn.close()


def save_pain_points(product_id: str, pain_points: List[PainPoint], conn: Optional[sqlite3.Connection] = None) -> None:
    own_conn = conn is None
    conn = conn or get_connection()
    now = _now()

    conn.execute("DELETE FROM pain_points WHERE product_id = ?", (product_id,))
    conn.executemany(
        "INSERT INTO pain_points "
        "(product_id, rank, pain_point, description, supporting_review_ids, supporting_quotes, "
        "verified_quote_count, needs_manual_review, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                product_id,
                pp.rank,
                pp.pain_point,
                pp.description,
                json.dumps(pp.supporting_review_ids),
                json.dumps(pp.supporting_quotes),
                pp.verified_quote_count,
                int(pp.needs_manual_review),
                now,
            )
            for pp in pain_points
        ],
    )
    conn.commit()
    logger.info("Saved %d pain points for %s", len(pain_points), product_id)
    if own_conn:
        conn.close()


def get_pain_points(product_id: str, conn: Optional[sqlite3.Connection] = None) -> List[Dict]:
    own_conn = conn is None
    conn = conn or get_connection()
    rows = conn.execute(
        "SELECT * FROM pain_points WHERE product_id = ? ORDER BY rank", (product_id,)
    ).fetchall()
    if own_conn:
        conn.close()
    return [
        {
            "product_id": row["product_id"],
            "rank": row["rank"],
            "pain_point": row["pain_point"],
            "description": row["description"],
            "supporting_review_ids": json.loads(row["supporting_review_ids"]),
            "supporting_quotes": json.loads(row["supporting_quotes"]),
            "verified_quote_count": row["verified_quote_count"],
            "needs_manual_review": bool(row["needs_manual_review"]),
        }
        for row in rows
    ]


def save_gap_opportunities(
    main_product_id: str, gap_batch: GapOpportunityBatch, conn: Optional[sqlite3.Connection] = None
) -> None:
    own_conn = conn is None
    conn = conn or get_connection()
    now = _now()

    conn.execute("DELETE FROM gap_opportunities WHERE main_product_id = ?", (main_product_id,))
    conn.executemany(
        "INSERT INTO gap_opportunities "
        "(main_product_id, competitor_product_id, competitor_pain_point, opportunity, rationale, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (main_product_id, op.competitor_product_id, op.competitor_pain_point, op.opportunity, op.rationale, now)
            for op in gap_batch.opportunities
        ],
    )
    conn.commit()
    logger.info("Saved %d gap opportunities for %s", len(gap_batch.opportunities), main_product_id)
    if own_conn:
        conn.close()


def log_llm_usage(
    agent: str,
    product_id: str,
    model: str,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    total_tokens: Optional[int],
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    own_conn = conn is None
    conn = conn or get_connection()
    conn.execute(
        "INSERT INTO llm_usage_log (timestamp, agent, product_id, model, input_tokens, output_tokens, total_tokens) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (_now(), agent, product_id, model, input_tokens, output_tokens, total_tokens),
    )
    conn.commit()
    if own_conn:
        conn.close()
