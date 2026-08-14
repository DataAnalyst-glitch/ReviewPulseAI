# ReviewPulse AI

**For sellers/clients:** ReviewPulse AI reads through your Amazon/Flipkart product reviews — and up to 3 competitors' — and turns them into a plain-English report: what customers love, their top complaints, and specific gaps where competitors are getting complained about but you could win the sale instead. You get a live dashboard and a clean PDF you can keep or share with your team.

- Live demo: _coming soon_
- Sample report: `sample_output/` (coming once Module 4 is built)

---

## For developers

Status: **Module 1 (Data Ingestion) only.** Modules 2–4 (RAG, agentic analysis, dashboards/PDF) are not built yet — see `CLAUDE.md` for the full build plan.

### Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in REVIEW_API_KEY only if you have one — optional
```

### Module 1 — Data Ingestion

Reviews are resolved in this order:

1. **CSV upload** (default, reliable path) — pass `csv_path` to `ingest_reviews()`.
2. **Live API** — only runs if `REVIEW_API_KEY` is set in `.env`. Any failure here (timeout, rate limit, bad response) falls back to step 3 instead of crashing.
3. **Bundled demo sample data** in `data/sample_reviews/` — used automatically if neither of the above is available, and every review from this path is flagged `is_demo_data=True`.

```python
from src.ingestion import ingest_reviews

reviews = ingest_reviews("DEMO-EARBUDS-A", csv_path="data/sample_reviews/DEMO-EARBUDS-A.csv")
# or, with no csv_path and no REVIEW_API_KEY set, falls back to bundled sample data:
reviews = ingest_reviews("DEMO-EARBUDS-B")
```

CSV input requirements: one column with the review text (`review_text`, `review`, `text`, `body`, `review_body`, or `content`), plus optional `rating`, `review_date`, `verified_purchase` columns. Any reviewer-identity columns (name, profile URL, username, email) are dropped before a review ever enters the pipeline — see `src/ingestion/csv_loader.py` PII handling.

Cleaned output is capped to 30–50 reviews per product and saved to `data/raw/` (git-ignored, regenerated per run). Logs go to `logs/app.log`.

### Tests

```bash
pytest
```

### Project structure

```
src/ingestion/     Module 1 — csv_loader, api_client, schema, orchestrator
src/utils/         logging_config
data/sample_reviews/  bundled demo CSVs (2 fictional products, for testing/fallback)
data/raw/          cleaned output per ingestion run (git-ignored)
tests/             pytest suite
```
