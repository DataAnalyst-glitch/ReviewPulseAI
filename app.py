"""
Module 4 — Streamlit presentation layer.

Keyword/ASIN -> live competitor discovery isn't built (no such API is wired
up — see Module 1's CSV-first design). Instead: enter a product id for the
seller's product and up to 3 competitors, optionally uploading a review CSV
for each; anything left without a CSV falls back to REVIEW_API_KEY (if set)
or bundled demo sample data, same as the ingestion pipeline always has.
"""

import json
import os
import time
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from src.analysis import AnalysisError, analyze_product, compare_products
from src.ingestion import IngestionError, ingest_reviews
from src.rag import RAGError, index_reviews
from src.report import build_comparison_report, disclaimer_text
from src.report.pdf_generator import generate_pdf_report
from src.report.voice_summary import build_voice_summary

# Same validated palette used by the PDF export (src/report/pdf_generator.py) —
# one color system across the whole product, not per-surface guesses.
COLOR_GOOD = "#0ca30c"
COLOR_CRITICAL = "#d03b3b"
COLOR_NEUTRAL = "#898781"
COLOR_SEQUENTIAL = "#2a78d6"
COLOR_SEQUENTIAL_DARK = "#184f95"
SENTIMENT_ORDER = ["Positive", "Neutral", "Negative"]
SENTIMENT_COLOR = {"Positive": COLOR_GOOD, "Neutral": COLOR_NEUTRAL, "Negative": COLOR_CRITICAL}

UPLOAD_DIR = Path("data") / "raw" / "uploads"

# Discovered from disk, not hardcoded, so any product added to
# data/sample_reviews/ is automatically both the form's default and (in
# demo mode) the full allowlist — one source of truth, no drift.
DEMO_PRODUCTS = tuple(sorted(p.stem for p in (Path("data") / "sample_reviews").glob("*.csv")))

# Business gate (not a security boundary): on the public Streamlit Cloud
# deployment, DEMO_MODE=true restricts analysis to the bundled sample
# products so visitors can't run the paid pipeline on their own data for
# free. Locally, leave DEMO_MODE unset for full functionality on real
# client orders. UI-layer only — ingestion/analysis/report code is
# unchanged and has no idea this flag exists.
DEMO_MODE = os.getenv("DEMO_MODE", "").strip().lower() in {"1", "true", "yes"}
DEMO_CONTACT_MESSAGE = (
    "To analyze your own product reviews, this is a paid service — "
    "contact **[your-email@example.com]** to order a custom report."
)

# Access-code unlock (paying clients running the live deployment directly,
# without the operator running it locally for them). Codes live in Streamlit
# Secrets / env as a simple comma-separated list — no DB, no expiry, per the
# brief's "keep this simple for now". Session-only: st.session_state resets
# per browser session, so an unlock never becomes a permanent public bypass.
ACCESS_CODES = {code.strip() for code in os.getenv("ACCESS_CODES", "").split(",") if code.strip()}

st.set_page_config(page_title="ReviewPulse AI", page_icon="📊", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1100px; }
    footer { visibility: hidden; }

    .rp-hero {
        background: linear-gradient(135deg, #2a78d6 0%, #184f95 100%);
        color: #ffffff;
        padding: 1.75rem 2.25rem;
        border-radius: 12px;
        margin-bottom: 1.75rem;
    }
    .rp-hero h1 { margin: 0; font-size: 1.9rem; font-weight: 700; }
    .rp-hero p { margin: 0.45rem 0 0 0; opacity: 0.92; font-size: 1.02rem; max-width: 46rem; }

    .rp-stat {
        position: relative;
        border-radius: 18px;
        padding: 1.1rem 1.15rem 0.95rem 1.15rem;
        min-height: 104px;
        overflow: hidden;
    }
    .rp-stat-icon {
        position: absolute;
        top: 0.7rem;
        right: 0.7rem;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    }
    .rp-stat-icon svg { width: 16px; height: 16px; }
    .rp-stat-label {
        font-size: 0.82rem;
        font-weight: 500;
        color: rgba(11, 11, 11, 0.62);
        margin: 0 0 0.2rem 0;
        padding-right: 2.4rem;
    }
    .rp-stat-value { font-size: 1.95rem; font-weight: 700; line-height: 1.15; margin: 0; }

    .rp-stat-blue   { background: linear-gradient(135deg, #dcecfc 0%, #f1f8ff 100%); }
    .rp-stat-blue .rp-stat-value { color: #184f95; }
    .rp-stat-blue .rp-stat-icon  { color: #2a78d6; }

    .rp-stat-green  { background: linear-gradient(135deg, #dcf5e1 0%, #f1fbf2 100%); }
    .rp-stat-green .rp-stat-value { color: #0b6b13; }
    .rp-stat-green .rp-stat-icon  { color: #0ca30c; }

    .rp-stat-amber  { background: linear-gradient(135deg, #fce9cd 0%, #fff6e9 100%); }
    .rp-stat-amber .rp-stat-value { color: #9a5b12; }
    .rp-stat-amber .rp-stat-icon  { color: #c9791c; }

    .rp-stat-purple { background: linear-gradient(135deg, #ede1fb 0%, #f8f2fe 100%); }
    .rp-stat-purple .rp-stat-value { color: #5b3aa0; }
    .rp-stat-purple .rp-stat-icon  { color: #7c4fd6; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Feather-style line icons, 24x24 viewBox, stroke="currentColor" so each
# picks up its card's accent color (set via .rp-stat-<variant> .rp-stat-icon).
_STAT_ICONS = {
    "reviews": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="6" y1="20" x2="6" y2="12"></line>'
        '<line x1="12" y1="20" x2="12" y2="8"></line>'
        '<line x1="18" y1="20" x2="18" y2="4"></line>'
        "</svg>"
    ),
    "positive": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="20 6 9 17 4 12"></polyline>'
        "</svg>"
    ),
    "pain": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="12 2 22 20 2 20"></polygon>'
        '<line x1="12" y1="9" x2="12" y2="14"></line>'
        '<line x1="12" y1="17" x2="12.01" y2="17"></line>'
        "</svg>"
    ),
    "gaps": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"></circle>'
        '<circle cx="12" cy="12" r="6"></circle>'
        '<circle cx="12" cy="12" r="2"></circle>'
        "</svg>"
    ),
}


def _stat_card(column, variant: str, icon_key: str, label: str, value: str) -> None:
    with column:
        st.markdown(
            f'<div class="rp-stat rp-stat-{variant}">'
            f'<div class="rp-stat-icon">{_STAT_ICONS[icon_key]}</div>'
            f'<p class="rp-stat-label">{label}</p>'
            f'<p class="rp-stat-value">{value}</p>'
            f"</div>",
            unsafe_allow_html=True,
        )

st.markdown(
    """
    <div class="rp-hero">
        <h1>📊 ReviewPulse AI</h1>
        <p>Turn Amazon &amp; Flipkart reviews into a sentiment breakdown, top customer pain points,
        and competitor feature-gap opportunities — in a few minutes.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


def _save_upload(uploaded_file, product_id: str) -> str | None:
    if uploaded_file is None:
        return None
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / f"{product_id}.csv"
    path.write_bytes(uploaded_file.getvalue())
    return str(path)


def _render_listen_button(summary_text: str) -> None:
    """
    Voice Output (Update Brief Addition 2) — browser-native Web Speech API
    (speechSynthesis), no paid service, no new Python dependency. Feature-
    detected client-side: if unsupported, the button says so instead of
    silently doing nothing, and the rest of the app (including the visible
    summary text right above this) works identically either way.
    """
    safe_text = json.dumps(summary_text)
    html = f"""
    <div style="font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; display: flex; align-items: center; gap: 0.6rem;">
      <button id="rp-listen-btn" style="
          background:#2a78d6; color:#fff; border:none; border-radius:8px;
          padding:0.5rem 1rem; font-size:0.95rem; font-weight:500; cursor:pointer;">
        🔊 Listen to Summary
      </button>
      <span id="rp-listen-status" style="color:#52514e; font-size:0.85rem;"></span>
    </div>
    <script>
      (function() {{
        const btn = document.getElementById('rp-listen-btn');
        const status = document.getElementById('rp-listen-status');
        const text = {safe_text};
        btn.addEventListener('click', function() {{
          if (!('speechSynthesis' in window)) {{
            status.textContent = 'Voice playback is not supported in this browser.';
            return;
          }}
          window.speechSynthesis.cancel();
          const utterance = new SpeechSynthesisUtterance(text);
          utterance.rate = 1.0;
          status.textContent = 'Playing...';
          utterance.onend = function() {{ status.textContent = 'Done.'; }};
          utterance.onerror = function() {{ status.textContent = 'Playback unavailable right now.'; }};
          window.speechSynthesis.speak(utterance);
        }});
      }})();
    </script>
    """
    components.html(html, height=45)


with st.sidebar:
    st.markdown("### Analyze a product")

    # Only relevant when DEMO_MODE is on — locally (DEMO_MODE unset) the app
    # is already fully unlocked, so this stays hidden and nothing changes.
    if DEMO_MODE and not st.session_state.get("access_unlocked", False):
        entered_code = st.text_input(
            "Have an access code? Enter it here to unlock full analysis",
            type="password",
            key="access_code_input",
        )
        if entered_code.strip():
            if entered_code.strip() in ACCESS_CODES:
                st.session_state["access_unlocked"] = True
                st.rerun()
            else:
                st.error("Invalid access code.")

    unlocked = st.session_state.get("access_unlocked", False)
    effective_demo_mode = DEMO_MODE and not unlocked

    if DEMO_MODE and unlocked:
        st.success("🔓 Access code accepted — full analysis unlocked for this session.")

    demo_list_str = " vs ".join(f"`{pid}`" for pid in DEMO_PRODUCTS) if DEMO_PRODUCTS else "the bundled samples"
    st.caption(f"No CSV or product data handy? Try the built-in demo pair — {demo_list_str} — already filled in below.")

    if effective_demo_mode:
        st.info(f"🔒 **Demo mode** — only the sample products above can be analyzed here. {DEMO_CONTACT_MESSAGE}")

    with st.form("analyze_form"):
        st.markdown("**Your product**")
        main_id = st.text_input(
            "Product ID or ASIN",
            value=DEMO_PRODUCTS[0] if DEMO_PRODUCTS else "",
            help="A short identifier you choose — used to label results and match an uploaded CSV.",
        )
        st.caption("🎤 Voice input — coming soon")
        main_csv = st.file_uploader(
            "Reviews CSV (optional)", type="csv", key="main_csv", disabled=effective_demo_mode,
            help="Disabled in demo mode — this is a paid service for your own data."
            if effective_demo_mode else
            "One row per review with a text column (review_text/review/text/body). Leave empty to use demo data.",
        )

        st.markdown("**Competitors** (up to 3, optional)")
        competitor_inputs = []
        for i in range(3):
            default = DEMO_PRODUCTS[1] if i == 0 and len(DEMO_PRODUCTS) > 1 else ""
            cid = st.text_input(f"Competitor {i + 1} ID", value=default, key=f"comp_id_{i}")
            ccsv = st.file_uploader(
                f"Competitor {i + 1} CSV (optional)", type="csv", key=f"comp_csv_{i}", disabled=effective_demo_mode,
            )
            competitor_inputs.append((cid.strip(), ccsv))

        submitted = st.form_submit_button("Analyze", type="primary", width="stretch")

    with st.expander("How this works"):
        st.markdown(
            "1. **Ingest** — reads your CSV, or falls back to a live API "
            "(if configured) or bundled demo data, so a run never fails on a missing upload.\n"
            "2. **Index** — chunks and embeds reviews for retrieval.\n"
            "3. **Analyze** — classifies sentiment and extracts top pain points per product, "
            "each backed by a verified quote from the source review.\n"
            "4. **Compare** — finds competitor complaints your product doesn't share, "
            "as feature-gap opportunities.\n\n"
            "Reviewer names and profile links are never stored (see `CLAUDE.md` Section 5.5)."
        )

if submitted:
    if not main_id.strip():
        st.error("Product ID is required.")
        st.stop()

    main_id = main_id.strip()
    competitors = [(cid, csv) for cid, csv in competitor_inputs if cid]

    if effective_demo_mode:
        attempted_ids = [main_id] + [cid for cid, _ in competitors]
        attempted_csvs = [main_csv] + [csv for _, csv in competitors]
        if any(pid not in DEMO_PRODUCTS for pid in attempted_ids) or any(csv is not None for csv in attempted_csvs):
            st.warning(f"This is a live demo using sample data. {DEMO_CONTACT_MESSAGE}")
            st.stop()

    seen_ids = {main_id}
    deduped_competitors = []
    dropped_ids = []
    for cid, csv_file in competitors:
        if cid in seen_ids:
            dropped_ids.append(cid)
            continue
        seen_ids.add(cid)
        deduped_competitors.append((cid, csv_file))
    competitors = deduped_competitors
    if dropped_ids:
        st.warning(f"Skipped duplicate product ID(s) already used elsewhere: {', '.join(dropped_ids)}")

    t0 = time.time()
    failed_ids = []

    with st.status("Running pipeline...", expanded=True) as status:
        for pid, csv_file in [(main_id, main_csv)] + competitors:
            try:
                st.write(f"Ingesting reviews for **{pid}**...")
                csv_path = _save_upload(csv_file, pid)
                reviews = ingest_reviews(pid, csv_path=csv_path)

                st.write(f"Indexing {len(reviews)} reviews for **{pid}**...")
                index_reviews(reviews)

                st.write(f"Analyzing sentiment and pain points for **{pid}**...")
                analyze_product(pid, reviews)
            except (IngestionError, RAGError, AnalysisError) as exc:
                st.warning(f"**{pid}** could not be analyzed: {exc}")
                failed_ids.append(pid)

        if main_id in failed_ids:
            status.update(label="Pipeline failed — see message above", state="error")
            st.stop()

        successful_competitors = [cid for cid, _ in competitors if cid not in failed_ids]
        if successful_competitors:
            st.write("Comparing against competitors for feature-gap opportunities...")
            try:
                compare_products(main_id, successful_competitors)
            except AnalysisError as exc:
                st.warning(f"Gap analysis failed: {exc}")
                successful_competitors = []

        status.update(label=f"Done in {time.time() - t0:.1f}s", state="complete")

    st.session_state["report"] = build_comparison_report(main_id, successful_competitors)

if "report" not in st.session_state:
    st.info(
        "**Get started:** the sidebar is already filled in with demo data — click **Analyze** to see "
        "a full run, or replace the product IDs and upload your own CSVs."
    )
    st.stop()

report = st.session_state["report"]
main = report.main

if main.is_demo_data:
    st.info(f"**{main.product_id}** is bundled demo data — not live-scraped reviews.")

st.header(f"Results — {main.product_id}")
st.caption(disclaimer_text(main.total_reviews))

positive_pct = (main.sentiment_counts.get("Positive", 0) / main.total_reviews * 100) if main.total_reviews else 0
metric_cols = st.columns(4)
_stat_card(metric_cols[0], "blue", "reviews", "Reviews analyzed", str(main.total_reviews))
_stat_card(metric_cols[1], "green", "positive", "Positive sentiment", f"{positive_pct:.0f}%")
_stat_card(metric_cols[2], "amber", "pain", "Pain points found", str(len(main.pain_points)))
_stat_card(
    metric_cols[3], "purple", "gaps", "Gap opportunities",
    str(len(report.gap_opportunities)) if report.competitors else "—",
)

with st.container(border=True):
    st.subheader("Sentiment Breakdown")
    col_chart, col_table = st.columns([2, 1])
    with col_chart:
        labels = [s for s in SENTIMENT_ORDER if main.sentiment_counts.get(s, 0) > 0]
        if labels:
            values = [main.sentiment_counts[s] for s in labels]
            colors = [SENTIMENT_COLOR[s] for s in labels]
            fig = go.Figure(data=[go.Pie(labels=labels, values=values, marker=dict(colors=colors), hole=0.4)])
            fig.update_traces(textinfo="label+percent", hovertemplate="%{label}: %{value} reviews<extra></extra>")
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280)
            st.plotly_chart(fig, width="stretch")
        else:
            st.write("No sentiment results.")
    with col_table:
        st.dataframe(
            {"Sentiment": SENTIMENT_ORDER, "Count": [main.sentiment_counts.get(s, 0) for s in SENTIMENT_ORDER]},
            hide_index=True,
            width="stretch",
        )

with st.container(border=True):
    st.subheader("Top Pain Points")
    if main.pain_points:
        pp_labels = [p["pain_point"] for p in main.pain_points]
        pp_counts = [len(p["supporting_review_ids"]) for p in main.pain_points]
        fig2 = go.Figure(data=[go.Bar(x=pp_counts, y=pp_labels, orientation="h", marker=dict(color=COLOR_SEQUENTIAL))])
        fig2.update_layout(
            yaxis=dict(autorange="reversed"), xaxis_title="Supporting reviews",
            margin=dict(t=10, b=10, l=10, r=10), height=220,
        )
        st.plotly_chart(fig2, width="stretch")

        for point in main.pain_points:
            flag = "⚠️ needs manual review" if point["needs_manual_review"] else f"✓ {point['verified_quote_count']} quote(s) verified"
            with st.expander(f"{point['rank']}. {point['pain_point']} — {flag}"):
                st.write(point["description"])
                for quote in point["supporting_quotes"]:
                    st.markdown(f"> {quote}")
                if point.get("recommended_action"):
                    st.markdown(f"**💡 Recommended action:** {point['recommended_action']}")
                if point.get("suggested_listing_copy"):
                    st.markdown(f"**📝 Suggested Listing Copy:** {point['suggested_listing_copy']}")
    else:
        st.write("No pain points identified.")

with st.container(border=True):
    st.subheader("Statistical Accuracy Check")
    st.caption(
        "📐 Statistical (pandas), not AI-generated — cross-checks each review's star rating against the AI's "
        "sentiment label, independent of the quote-verification check above."
    )
    if not main.has_rating_data:
        st.info("No star-rating data available for this product — skipping the rating-based accuracy check.")
    elif main.sentiment_mismatches:
        st.warning(f"{len(main.sentiment_mismatches)} review(s) flagged: star rating and AI sentiment disagree.")
        st.dataframe(
            [
                {
                    "Rating": f"{row['rating']:.0f} stars",
                    "AI sentiment": row["sentiment"],
                    "Review": row["review_text"],
                    "Flag": row["mismatch_reason"],
                }
                for row in main.sentiment_mismatches
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.success("No sentiment mismatches found — star ratings and AI sentiment agree across all reviews.")

with st.container(border=True):
    st.subheader("Review Timeline")
    st.caption("📐 Statistical (pandas), not AI-generated — pain-point mention frequency over time, a proxy signal since sales/demographic data isn't available from reviews.")
    if not main.pain_point_timeline:
        st.info("Not enough review-date data to build a timeline for this product.")
    else:
        timeline_colors = [COLOR_SEQUENTIAL, "#c9791c", "#7c4fd6", COLOR_NEUTRAL]
        pain_point_order = [p["pain_point"] for p in main.pain_points]
        fig3 = go.Figure()
        for i, pain_point in enumerate(pain_point_order):
            points = [row for row in main.pain_point_timeline if row["pain_point"] == pain_point]
            if not points:
                continue
            fig3.add_trace(
                go.Scatter(
                    x=[row["period"] for row in points],
                    y=[row["count"] for row in points],
                    mode="lines+markers",
                    name=pain_point,
                    line=dict(color=timeline_colors[i % len(timeline_colors)], width=2),
                    marker=dict(size=7),
                )
            )
        fig3.update_layout(
            xaxis_title="Week", yaxis_title="Mentions", margin=dict(t=10, b=10, l=10, r=10), height=280,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig3, width="stretch")

        for row in main.pain_point_trend:
            trend_icon = {"increasing": "📈", "new/rising": "📈", "decreasing": "📉", "steady": "➡️"}.get(row["trend"], "")
            st.caption(
                f"{trend_icon} **{row['pain_point']}**: {row['earlier_count']} mention(s) earlier vs "
                f"{row['later_count']} mention(s) later — {row['trend']}."
            )

if report.competitors:
    with st.container(border=True):
        st.subheader("Statistical Comparison")
        st.caption("📐 Statistical (pandas groupby), not AI-generated — hard numbers alongside the AI-generated gap opportunities below.")
        st.dataframe(
            [
                {
                    "Product": row["product_id"],
                    "Reviews": row["review_count"],
                    "Avg rating": f"{row['avg_rating']:.2f}" if row["avg_rating"] is not None else "N/A",
                    "Positive %": f"{row['positive_pct']:.0f}%",
                    "Neutral %": f"{row['neutral_pct']:.0f}%",
                    "Negative %": f"{row['negative_pct']:.0f}%",
                }
                for row in report.comparison_table
            ],
            hide_index=True,
            width="stretch",
        )

    with st.container(border=True):
        st.subheader("Feature Gap Opportunities")
        st.caption("🤖 AI-generated — interpreted opportunities from the LLM analysis, complementing the statistical comparison above.")
        if report.gap_opportunities:
            st.dataframe(report.gap_opportunities, hide_index=True, width="stretch")
        else:
            st.write("No gap opportunities identified.")

        for competitor in report.competitors:
            with st.expander(f"Competitor detail — {competitor.product_id}"):
                st.write(f"Total reviews: {competitor.total_reviews}")
                st.write(f"Sentiment: {competitor.sentiment_counts}")
                for point in competitor.pain_points:
                    st.write(f"{point['rank']}. {point['pain_point']} — {point['description']}")

st.subheader("Voice Summary")
voice_summary = build_voice_summary(report)
st.info(voice_summary)
_render_listen_button(voice_summary)

st.subheader("Export")
pdf_bytes = generate_pdf_report(report)
st.download_button(
    "📄 Generate Report (PDF)",
    data=pdf_bytes,
    file_name=f"{main.product_id}_reviewpulse_report.pdf",
    mime="application/pdf",
    type="primary",
)
