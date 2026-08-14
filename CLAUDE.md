# ReviewPulse AI — Project Brief for Claude Code

> Paste this entire document into Claude Code (`claude` in your project terminal) as the first message, or save it as `CLAUDE.md` in your project root so Claude Code reads it automatically every session.

---

## 1. What We're Building

**ReviewPulse AI** — an AI-powered tool that lets an Amazon/Flipkart seller enter a product keyword or ASIN, automatically pulls reviews for that product AND up to 3 competitor products, and produces:

1. Sentiment breakdown (Positive/Neutral/Negative)
2. Top 3 recurring customer pain points per product
3. A "Feature Gap Opportunity" comparison — what competitors' customers complain about that this seller could exploit
4. A visual dashboard (Streamlit for live demo + Power BI for a polished client-facing report)

**Primary purpose:** This is a freelance portfolio project. It will be sold as a **done-for-you report service** to small Amazon/Flipkart sellers on Fiverr/Upwork, not as a self-serve SaaS product initially. Every technical decision should optimize for: (a) a fast, working demo, (b) a professional client-facing PDF/report output, (c) low/zero running cost.

---

## 2. Tech Stack (do not deviate without asking)

|Layer|Technology|
|-|-|
|Frontend/Demo UI|Streamlit (Python)|
|Backend/Agent orchestration|Python, LangChain, ~~CrewAI~~ (see deviation below)|
|LLM|Google Gemini API (free tier)|
|Database + Vector store|Supabase (PostgreSQL + pgvector), currently Chroma+SQLite locally (see deviation below)|
|Client-facing analytics|Power BI Desktop (live Supabase connector)|
|Secrets|`.env` file, never hardcoded, never committed|

**Approved deviations (asked, user confirmed):**

- **CrewAI dropped, plain LangChain used instead.** CrewAI's dependency chain pulls in `langchain<0.2`, which pins `numpy<2` — no prebuilt wheel exists for this machine's Python 3.14 and it can't build from source (no C compiler installed). Agents A/B/C (Module 3) are implemented as direct `langchain-google-genai` calls with Pydantic structured output instead.
- **Supabase deferred, local storage used instead.** Module 2 (vectors) uses a local Chroma store (`data/vector_store/`); Module 3 (structured analysis results) uses local SQLite (`data/reviewpulse.db`). Both are designed as drop-in swaps for Supabase pgvector/Postgres — only the storage-layer module needs to change when Supabase is set up, not the agent/RAG logic.

---

## 3. Build Order (follow this sequence, one module at a time — do not jump ahead)

**Module 1 — Data Ingestion**

* Input: product keyword or ASIN
* Output: 30-50 cleaned reviews per product, stored raw
* IMPORTANT (see Section 5, point 1): use a legitimate data source, not raw scraping of amazon.com

**Module 2 — RAG / Vector Storage**

* Chunk reviews with LangChain text splitters
* Generate embeddings with a free embedding model
* Store in Supabase pgvector

**Module 3 — Agentic Analysis**

* Agent A: sentiment classification per review (Positive/Neutral/Negative)
* Agent B: extract top 3 recurring pain points, structured JSON output
* Agent C: cross-product comparison → "Feature Gap Opportunities"
* Save all structured results back to Supabase

**Module 4 — Presentation Layer**

* Streamlit UI: keyword input → charts (sentiment pie, pain-point bar, gap table) in under 2 minutes
* Power BI dashboard: same data via live Supabase connector, for client-facing polish
* PDF export of the final report (see Section 5, point 6 — this is a new addition, treat as required, not optional)

Build and manually test each module before moving to the next. After each module, show me the output so I can sanity-check before we proceed.

---

## 4. Non-Functional Requirements

* Full pipeline (ingest → RAG → analysis → save) under 60 seconds
* Must run on 100% free tiers (Supabase free tier, Streamlit Community Cloud, Gemini free tier)
* All API keys in `.env`, `.env` in `.gitignore` — verify this before first commit
* Code should be clean enough to screen-record as a portfolio demo

---

## 5. What a Senior AI Engineer Would Add (things the original plan missed — please implement these too)

1. **Legal/ToS-safe data sourcing.** Directly scraping amazon.com with BeautifulSoup/Selenium violates Amazon's Terms of Service and can get IPs blocked — this is a real risk for a client-facing product. Use one of:

   * A legitimate product-data API (e.g., Rainforest API, SerpApi's Amazon Reviews API — both have limited free/trial tiers suitable for a demo)
   * A public review dataset (e.g., Amazon Reviews dataset on Kaggle/HuggingFace) for the portfolio demo, clearly labeled as "demo data," with real-API integration offered as the paid client deliverable
   * Manually client-supplied review exports/CSV as a fallback input mode — build this as **the reliable default**, and treat live scraping as a bonus, not the load-bearing path
2. **Graceful degradation & error handling.** API rate limits, empty review sets, and malformed data are the most common demo-failure points in front of a client. Every module needs try/except with a user-visible fallback message, not a stack trace on screen.
3. **Cost/rate-limit tracking for the LLM calls.** Even on free tiers, track token usage per run and log it, so you know your real per-report cost before pricing your Fiverr gig.
4. **A lightweight evaluation check on the agent's output**, not just raw generation. Pain-point extraction from LLMs can hallucinate specifics that aren't in the source reviews. Add a simple guardrail: the pain-point agent must quote or closely paraphrase the specific review chunk it drew a claim from, and you spot-check 5-10 outputs manually before showing any client demo.
5. **PII handling.** Reviewer usernames/profile links should be stripped or anonymized before storage — don't store or display identifiable reviewer data in the dashboard.
6. **Client-facing PDF export — add this as a new feature, not in the original PRD.** A live Streamlit link is great for a demo, but paying clients expect a clean, brandable PDF/report they can keep, forward, or show their team. Add a "Generate Report" button that exports the dashboard's key findings (sentiment summary, top pain points, gap table) as a formatted PDF. This single feature does more for "will they actually pay" than any dashboard polish.
7. **A `sample_output/` folder in the repo** with one fully-run example (input keyword → final PDF/report), committed to the repo. This is what you'll actually paste into your Fiverr gig and cold outreach messages — it needs to exist before Day 9 of the plan, not be generated live each time.
8. **Basic logging**, not for scale, but so that when a demo fails during a client call you can see why in under a minute.
9. **README written for two audiences** — one section for a developer who wants to run the code, one short section at the top written for a non-technical client/recruiter skimming your GitHub, explaining in plain English what this tool does and linking the live demo + sample PDF.

---

## 6. Immediate Task for This Session

Start with **Module 1 (Data Ingestion)** using the fallback-safe design from Section 5, point 1: build the pipeline so it accepts either (a) a manually uploaded CSV/export of reviews, or (b) a call to a review-data API if a key is present in `.env` — with (a) as the default working path so the demo never breaks. Ask me for my Supabase and Gemini API keys setup status before writing DB code. Confirm the folder structure with me before generating files.

---

## 7. Update Brief — Phase 2 (Differentiation Additions)

> Given after Modules 1–4 were complete and deployed. Goal: differentiate from Helium 10 / Jungle Scout by fixing their specific weaknesses — raw data with no guidance, and no accessibility for non-technical sellers.

**Addition 1 — Recommendation Agent (Agent D, added to Module 3).** Runs after Agents A/B/C. For each pain point / feature gap, adds ONE short, concrete, actionable `recommended_action` line grounded in the actual evidence — not generic advice. Guardrail: if it can't be grounded, it must say "Insufficient data for a specific recommendation." instead of inventing one.

**Status: implemented** (`src/analysis/agents.py`: `run_pain_point_recommendations`, `run_gap_recommendations`). Flows into the existing dashboard (pain-point expanders, gap table) and PDF — no new UI sections, matching the brief's "no new UI needed, just a new column" instruction. A failure in this step is logged and swallowed rather than raised, since it's an enhancement on top of already-successful sentiment/pain-point/gap results, not something that should take down the whole report.

**Addition 2 — Voice Input & Voice Output (Module 4, "wow" differentiator, never blocks core text-input pipeline).** Priority order given: (1) Recommendation Agent, (2) Voice Output (spoken 3-point summary), (3) Voice Input (mic), do last and only if time allows — ship 1+2 and mark 3 "coming soon" if tight on time.

**Status:** Voice Output shipped (`app.py` "Listen to Summary" button + `src/report/voice_summary.py`, verified live). Voice Input marked "coming soon" in the sidebar per this brief's own explicit fallback — evaluated feasible dependency-wise (`streamlit-mic-recorder` installs cleanly) but deferred: transcription would depend on an undocumented free Google STT endpoint (reliability risk for a paying client) and there's no way to verify real microphone capture end-to-end in an automated/headless environment with no hardware mic. User confirmed this call when asked.

---

## 8. Business Gate — Demo Mode

> Given after the public Streamlit Cloud link was live and shared as a free demo. The actual service is sold per-report (Fiverr/Upwork) — the public link needed to stop being usable as a free substitute for that.

**`DEMO_MODE` env var (`app.py`, UI-layer only — ingestion/RAG/analysis/report code is unchanged and unaware this flag exists).** When `true`: only the bundled sample products (`DEMO_PRODUCTS`, discovered from `data/sample_reviews/*.csv` at runtime, not hardcoded) can be analyzed; any other product ID or an uploaded CSV (main or competitor) shows a friendly "this is a paid service" message and stops before running the pipeline; CSV upload widgets are also disabled outright. Unset (default, including local `.env`) → full functionality, for running real client orders.

**Deployed:** Streamlit Cloud Secrets has `DEMO_MODE = "true"` (public link, demo-only). Local `.env` leaves it unset (full functionality for paid orders). Both modes verified locally in-browser before pushing: full mode ran a non-demo product ID through the normal pipeline (and failed with the ordinary `IngestionError`, not a gate message); demo mode blocked both a non-demo main ID and a non-demo competitor ID with the gate message, and ran the default demo pair normally.

---

## 9. Update Brief — Sample Size, Trust, and Listing Copy

> Given after the DEMO_MODE gate shipped. Five features, in priority order, each implemented/tested/committed/pushed separately: (1) Suggested Listing Copy, (2) sample size increase, (3) trust/accuracy disclaimer, (4) Voice Output re-verification against a tighter 30-45s spec, (5) Voice Input if time allows.

**Addition 1 — Suggested Listing Copy.** For each pain point with a groundable `recommended_action`, Agent D's same call also produces `suggested_listing_copy`: one ready-to-use, Amazon-style listing bullet (<=200 characters, benefit-focused) addressing that pain point, grounded in the same verified evidence. Suppressed (not the fallback string) whenever `recommended_action` is the insufficient-data fallback. **Status: implemented and verified live** (`src/analysis/schemas.py`, `agents.py`, `storage.py` migration, Streamlit expander, PDF export).

**Addition 2 — Sample size increase (30-50 -> 200-300 reviews).** Supersedes Section 4's "under 60 seconds" NFR for the full pipeline — user explicitly authorized "a few minutes is fine" for this change after being shown the tradeoff. The real risk found and flagged before implementing: Agent A (sentiment) returns one structured JSON result per review in a single call, so at 300 reviews a single call risked the model's output-token limit and truncated/unparseable JSON (this exact failure class was independently observed minutes earlier from an unrelated transient rate-limit error during test runs). User chose to batch Agent A into 50-review chunks (`SENTIMENT_BATCH_SIZE` in `src/analysis/agents.py`) rather than raise the cap on the single-call design or compromise on a smaller cap. Agents B/C/D output a small fixed-size result regardless of review count, so they stay single-call — no batching needed there. Local embedding/RAG (Module 2) was not a cost/reliability concern either way — it's free and fast at any review count tested.

**Addition 3 — Trust/accuracy disclaimer.** Short, professional disclaimer on both the Streamlit results page and the PDF: review-text-only analysis, N reviews analyzed, doesn't incorporate sales/pricing/market data, use alongside business judgment. **Status: implemented and verified live** — one shared `disclaimer_text()` in `src/report/__init__.py` so both surfaces can't drift; PDF version renders in the page footer (every page, via `ReportPDF.footer()`), Streamlit version as a caption under the results header.

**Addition 4 — Voice Output, re-verified against a 30-45 second spec.** Was already shipped (Section 7 Addition 2); this update brief asked for a specific 30-45 second length, tighter than the original 3-point-summary spec produced (which ran ~15-20s). **Status: implemented and verified live.** `build_voice_summary()` expanded (still template-built from already-known structured results, no new LLM call, still grounded — the added length comes from the pain point's own already-generated description, not invented text) to land at ~85-95 words on real demo data, ~30-35s at a typical browser TTS rate. Verified live: visible summary text and "Listen to Summary" button (speechSynthesis, status -> "Playing...") both confirmed working with the longer text.

**Addition 5 — Voice Input.** Lowest priority, explicitly OK to leave "coming soon" if time/blockers arise, per this brief's own instruction. **Status: deferred, stays "coming soon".** This round's version of the browser's native SpeechRecognition API removes last time's blocker (no Python STT dependency needed - transcription is fully client-side), but surfaced a different one: `components.html()` runs in a sandboxed iframe with no officially-supported way to write a transcribed string back into a native `st.text_input` - only options are (a) a full two-way Streamlit custom component (real JS build infrastructure for one field) or (b) a top-level-navigation query-param hack that's plausible but unverifiable here (no hardware mic in this environment to test the actual mic-to-textbox round trip). User confirmed leaving it deferred rather than shipping something unverified when asked.
