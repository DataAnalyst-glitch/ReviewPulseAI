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
