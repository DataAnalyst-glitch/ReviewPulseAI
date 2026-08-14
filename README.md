# ReviewPulse AI

**For sellers/clients:** ReviewPulse AI reads through your Amazon/Flipkart product reviews — and up to 3 competitors' — and turns them into a plain-English report: what customers love, their top complaints, and specific gaps where competitors are getting complained about but you could win the sale instead. You get a live dashboard and a clean PDF you can keep or share with your team.

- Live demo: _coming soon_
- Sample report: `sample_output/` (coming once Module 4 is built)

---

## For developers

Status: **Modules 1–2 (Data Ingestion, RAG/Vector Storage).** Modules 3–4 (agentic analysis, dashboards/PDF) are not built yet — see `CLAUDE.md` for the full build plan.

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

### Module 2 — RAG / Vector Storage

Backed by a **local Chroma store** (`data/vector_store/`, git-ignored) instead of Supabase pgvector — Supabase setup is deferred. Both are accessed as a LangChain vector store, so swapping the backend later is a change to `src/rag/vector_store.py` only. Embeddings come from a local, free HuggingFace model (`sentence-transformers/all-MiniLM-L6-v2`) — no API key, no rate limits.

```python
from src.ingestion import ingest_reviews
from src.rag import index_reviews, retrieve_relevant_chunks

reviews = ingest_reviews("DEMO-EARBUDS-A", csv_path="data/sample_reviews/DEMO-EARBUDS-A.csv")
index_reviews(reviews)

chunks = retrieve_relevant_chunks("battery draining fast", product_id="DEMO-EARBUDS-A", k=3)
```

Each indexed chunk's metadata carries the full original review text (`original_review_text`) and a stable `review_id` — Module 3's pain-point agent will need to cite back to the exact source review as a hallucination guardrail (brief Section 5.4). Re-indexing the same reviews is a safe no-op (chunk ids are deterministic).

### Tests

```bash
pytest
```

### Project structure

```
src/ingestion/     Module 1 — csv_loader, api_client, schema, orchestrator
src/rag/           Module 2 — chunking, embeddings, vector_store, orchestrator
src/utils/         logging_config
data/sample_reviews/  bundled demo CSVs (2 fictional products, for testing/fallback)
data/raw/          cleaned output per ingestion run (git-ignored)
data/vector_store/ local Chroma index (git-ignored)
tests/             pytest suite
```
