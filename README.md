# ReviewPulse AI

**For sellers/clients:** ReviewPulse AI reads through your Amazon/Flipkart product reviews — and up to 3 competitors' — and turns them into a plain-English report: what customers love, their top complaints, and specific gaps where competitors are getting complained about but you could win the sale instead. You get a live dashboard and a clean PDF you can keep or share with your team.

- Live demo: _coming soon_ (not yet deployed to Streamlit Community Cloud)
- Sample report: [`sample_output/DEMO-EARBUDS-A_sample_report.pdf`](sample_output/DEMO-EARBUDS-A_sample_report.pdf) — a fully-run example on bundled demo data

---

## For developers

Status: **Modules 1–4 (Data Ingestion, RAG/Vector Storage, Agentic Analysis, Presentation Layer).** All four build-order modules from `CLAUDE.md` are implemented; see that file for approved tech-stack deviations. Not yet deployed to Streamlit Community Cloud, and Power BI / Supabase are still deferred (see Module 4 below).

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

Cleaned output is capped to 200–300 reviews per product and saved to `data/raw/` (git-ignored, regenerated per run). Logs go to `logs/app.log`.

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

Four agents, each batched into as few Gemini calls per product as possible (not one call per review, to stay well within free-tier rate limits):

- **Agent A (sentiment)** — classifies every review as Positive/Neutral/Negative. Chunked into 50-review calls (`SENTIMENT_BATCH_SIZE`) rather than one call for the whole product: this is the one agent whose output size scales directly with review count (one JSON result per review), so at the 200-300 review cap a single call risks the model's output-token limit and truncated/unparseable JSON. Agents B/C/D below always produce a small, fixed-size result regardless of review count, so they stay single-call.
- **Agent B (pain points)** — extracts the top 3 recurring complaints, each with supporting review ids and verbatim supporting quotes.
- **Agent C (gap analysis)** — compares the main product's pain points against up to 3 competitors' and surfaces "Feature Gap Opportunities": competitor complaints the seller's product doesn't share.
- **Agent D (recommendations)** — Phase 2 addition (`CLAUDE.md` Section 7). Turns each of the main product's pain points and each gap opportunity into ONE concrete, actionable `recommended_action` line grounded in the evidence (e.g. "Update the A+ content and main feature bullet points to explicitly highlight..."), not generic advice. If it can't ground a recommendation, it says so ("Insufficient data for a specific recommendation.") instead of inventing one. For pain points specifically, the same call also produces `suggested_listing_copy` — one ready-to-use, Amazon-style listing bullet (under 200 characters) addressing that pain point, grounded in the same evidence, suppressed whenever `recommended_action` is the insufficient-data fallback. A failure here is logged and swallowed, not raised — it's an enhancement on already-successful results.

Uses **plain LangChain + Gemini structured output**, not CrewAI — see the deviation note in `CLAUDE.md` (CrewAI's dependency chain doesn't install on this machine's Python 3.14). Model is `gemini-flash-lite-latest`: an alias (not a dated model id), because Gemini deprecates specific versions for new API keys often — `gemini-2.5-flash` and `gemini-2.5-flash-lite` both 404'd as "no longer available to new users" during development. The plain `gemini-flash-latest` alias also works but resolves to a reasoning/"thinking" model with only a 20-requests/day free quota, too restrictive for repeated demo runs; Flash-Lite has no reasoning overhead and is more than capable for this task.

```python
from src.analysis import analyze_product, compare_products

result = analyze_product("DEMO-EARBUDS-A", reviews)  # {"sentiment": ..., "pain_points": [...]}
gaps = compare_products("DEMO-EARBUDS-A", ["DEMO-EARBUDS-B"])  # run analyze_product on all products first
```

**Guardrail (brief Section 5.4):** every supporting quote Agent B produces is checked against the actual source review text (`src/analysis/guardrail.py`) — verbatim match or close paraphrase. Pain points with zero verifiable quotes are flagged `needs_manual_review=True` rather than silently trusted. This is an aid to the required manual step, not a replacement for it — **still spot-check 5-10 outputs by hand before showing a client demo.**

Results persist to local SQLite (`data/reviewpulse.db`, git-ignored) — a stand-in for Supabase, same reasoning as Module 2's Chroma store. Every LLM call's token usage is logged to the `llm_usage_log` table (brief Section 5.3) so real per-report cost is knowable before pricing a Fiverr gig.

### Module 4 — Presentation Layer

`app.py` (repo root, for Streamlit Community Cloud's default entry-file convention) is the UI:

```bash
streamlit run app.py
```

Enter a product ID (default `DEMO-EARBUDS-A`) and up to 3 competitor IDs, optionally uploading a review CSV for each — same fallback chain as Module 1 (CSV → live API → bundled demo data), so the demo never breaks on a missing upload. "Analyze" runs the full ingest → index → sentiment/pain-points → gap-comparison pipeline with per-product error handling (a failed competitor is skipped with a warning, not a crash) and shows:

- **Sentiment pie chart** — fixed status colors (green=Positive, gray=Neutral, red=Negative), not arbitrary categorical hues, since sentiment is a state, not an identity. Colors are the validated status palette from the dataviz skill's reference instance, not picked by eye.
- **Pain-point bar chart** — single sequential blue hue, ranked by how many reviews support each point.
- **Feature Gap Opportunities table.**
- **"Generate Report (PDF)"** button (brief Section 5.6) — exports the same findings as a formatted, brandable PDF via `src/report/pdf_generator.py` (fpdf2, same validated color roles as the charts). No chart-image embedding (would need `kaleido`, an extra dependency with its own compatibility risk) — bars are drawn directly as filled rectangles instead.
- **"Listen to Summary" (Voice Output, `CLAUDE.md` Section 7 Addition 2)** — a template-built 3-point spoken summary (sentiment split, #1 pain point, #1 recommendation; `src/report/voice_summary.py`, no LLM call — the numbers are already known, this is formatting) played via the browser's native `speechSynthesis` (Web Speech API, zero cost, zero new Python dependency). The summary text is always shown visibly above the button — never audio-only — and the same text is a fallback "Executive Summary" section at the top of the PDF, so the report doesn't depend on audio playback. Feature-detected client-side: browsers without `speechSynthesis` get a message instead of a silent failure, and the rest of the app works identically either way.

**Demo mode gate (`DEMO_MODE` env var):** the public Streamlit Cloud link is shared as a free demo, but the actual service is sold per-report — so `DEMO_MODE=true` (set in that deployment's Secrets) restricts analysis to the bundled sample products only (`DEMO_PRODUCTS`, discovered from `data/sample_reviews/*.csv`, not hardcoded). Typing any other product ID or uploading a CSV shows a friendly "this is a paid service" message instead of running the pipeline; CSV upload widgets are also disabled outright in this mode. Leave `DEMO_MODE` unset (the default, including in `.env` locally) for full functionality — any product ID, any uploaded CSV — for running real client orders on your own machine. This is a UI-layer gate only (`app.py`); ingestion/RAG/analysis/report code has no knowledge of it.

Power BI's live Supabase connector and Supabase itself remain deferred — Module 4 reads from the local SQLite/Chroma stores Modules 2–3 already write to. `src/report/__init__.py` is a read-only view over stored results (no LLM calls), so the Streamlit UI and PDF generator both build from the same data without re-running analysis.

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
src/report/        Module 4 — report data view, pdf_generator
src/utils/         logging_config
app.py             Module 4 — Streamlit UI (repo root, for Streamlit Cloud's entry-file convention)
data/sample_reviews/  bundled demo CSVs (2 fictional products, for testing/fallback)
data/raw/          cleaned output per ingestion run + uploaded CSVs (git-ignored)
data/vector_store/ local Chroma index (git-ignored)
data/reviewpulse.db  local SQLite results + token usage log (git-ignored)
sample_output/     one committed fully-run example (input -> PDF), for portfolio/gig use
tests/             pytest suite
```
