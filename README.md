# ReviewPulse AI

**For sellers/clients:** ReviewPulse AI reads through your Amazon/Flipkart product reviews — and up to 3 competitors' — and turns them into a plain-English report: what customers love, their top complaints, and specific gaps where competitors are getting complained about but you could win the sale instead. You get a live dashboard and a clean PDF you can keep or share with your team.

- Live demo: _coming soon_
- Sample report: `sample_output/` (coming once Module 4 is built)

---

## For developers

Status: **Modules 1–3 (Data Ingestion, RAG/Vector Storage, Agentic Analysis).** Module 4 (dashboards/PDF) is not built yet — see `CLAUDE.md` for the full build plan and approved tech-stack deviations.

### Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in REVIEW_API_KEY only if you have one — optional
# add your Gemini API key to .env as GEMINI_API_KEY= — required for Module 3
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

### Module 3 — Agentic Analysis

Three agents, each a single batched Gemini call per product (not one call per review, to stay well within free-tier rate limits and the 60-second pipeline budget):

- **Agent A (sentiment)** — classifies every review as Positive/Neutral/Negative.
- **Agent B (pain points)** — extracts the top 3 recurring complaints, each with supporting review ids and verbatim supporting quotes.
- **Agent C (gap analysis)** — compares the main product's pain points against up to 3 competitors' and surfaces "Feature Gap Opportunities": competitor complaints the seller's product doesn't share.

Uses **plain LangChain + Gemini structured output**, not CrewAI — see the deviation note in `CLAUDE.md` (CrewAI's dependency chain doesn't install on this machine's Python 3.14). Model is `gemini-flash-lite-latest`: an alias (not a dated model id), because Gemini deprecates specific versions for new API keys often — `gemini-2.5-flash` and `gemini-2.5-flash-lite` both 404'd as "no longer available to new users" during development. The plain `gemini-flash-latest` alias also works but resolves to a reasoning/"thinking" model with only a 20-requests/day free quota, too restrictive for repeated demo runs; Flash-Lite has no reasoning overhead and is more than capable for this task.

```python
from src.analysis import analyze_product, compare_products

result = analyze_product("DEMO-EARBUDS-A", reviews)  # {"sentiment": ..., "pain_points": [...]}
gaps = compare_products("DEMO-EARBUDS-A", ["DEMO-EARBUDS-B"])  # run analyze_product on all products first
```

**Guardrail (brief Section 5.4):** every supporting quote Agent B produces is checked against the actual source review text (`src/analysis/guardrail.py`) — verbatim match or close paraphrase. Pain points with zero verifiable quotes are flagged `needs_manual_review=True` rather than silently trusted. This is an aid to the required manual step, not a replacement for it — **still spot-check 5-10 outputs by hand before showing a client demo.**

Results persist to local SQLite (`data/reviewpulse.db`, git-ignored) — a stand-in for Supabase, same reasoning as Module 2's Chroma store. Every LLM call's token usage is logged to the `llm_usage_log` table (brief Section 5.3) so real per-report cost is knowable before pricing a Fiverr gig.

### Tests

```bash
pytest
```

The one test requiring a live `GEMINI_API_KEY` is skipped automatically if it's not set.

### Project structure

```
src/ingestion/     Module 1 — csv_loader, api_client, schema, orchestrator
src/rag/           Module 2 — chunking, embeddings, vector_store, orchestrator
src/analysis/      Module 3 — agents (sentiment/pain-points/gaps), guardrail, storage, orchestrator
src/utils/         logging_config
data/sample_reviews/  bundled demo CSVs (2 fictional products, for testing/fallback)
data/raw/          cleaned output per ingestion run (git-ignored)
data/vector_store/ local Chroma index (git-ignored)
data/reviewpulse.db  local SQLite results + token usage log (git-ignored)
tests/             pytest suite
```
