"""
Module 4 — Streamlit presentation layer.

Keyword/ASIN -> live competitor discovery isn't built (no such API is wired
up — see Module 1's CSV-first design). Instead: enter a product id for the
seller's product and up to 3 competitors, optionally uploading a review CSV
for each; anything left without a CSV falls back to REVIEW_API_KEY (if set)
or bundled demo sample data, same as the ingestion pipeline always has.
"""

import time
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from src.analysis import AnalysisError, analyze_product, compare_products
from src.ingestion import IngestionError, ingest_reviews
from src.rag import RAGError, index_reviews
from src.report import build_comparison_report
from src.report.pdf_generator import generate_pdf_report

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
DEMO_PRODUCTS = ("DEMO-EARBUDS-A", "DEMO-EARBUDS-B")

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
        and competitor feature-gap opportunities — in under two minutes.</p>
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


with st.sidebar:
    st.markdown("### Analyze a product")
    st.caption(
        f"No CSV or product data handy? Try the built-in demo pair — "
        f"`{DEMO_PRODUCTS[0]}` vs `{DEMO_PRODUCTS[1]}` — already filled in below."
    )

    with st.form("analyze_form"):
        st.markdown("**Your product**")
        main_id = st.text_input(
            "Product ID or ASIN", value=DEMO_PRODUCTS[0], help="A short identifier you choose — used to label results and match an uploaded CSV."
        )
        main_csv = st.file_uploader(
            "Reviews CSV (optional)", type="csv", key="main_csv",
            help="One row per review with a text column (review_text/review/text/body). Leave empty to use demo data.",
        )

        st.markdown("**Competitors** (up to 3, optional)")
        competitor_inputs = []
        for i in range(3):
            default = DEMO_PRODUCTS[1] if i == 0 else ""
            cid = st.text_input(f"Competitor {i + 1} ID", value=default, key=f"comp_id_{i}")
            ccsv = st.file_uploader(f"Competitor {i + 1} CSV (optional)", type="csv", key=f"comp_csv_{i}")
            competitor_inputs.append((cid.strip(), ccsv))

        submitted = st.form_submit_button("Analyze", type="primary", use_container_width=True)

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
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("No sentiment results.")
    with col_table:
        st.dataframe(
            {"Sentiment": SENTIMENT_ORDER, "Count": [main.sentiment_counts.get(s, 0) for s in SENTIMENT_ORDER]},
            hide_index=True,
            use_container_width=True,
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
        st.plotly_chart(fig2, use_container_width=True)

        for point in main.pain_points:
            flag = "⚠️ needs manual review" if point["needs_manual_review"] else f"✓ {point['verified_quote_count']} quote(s) verified"
            with st.expander(f"{point['rank']}. {point['pain_point']} — {flag}"):
                st.write(point["description"])
                for quote in point["supporting_quotes"]:
                    st.markdown(f"> {quote}")
    else:
        st.write("No pain points identified.")

if report.competitors:
    with st.container(border=True):
        st.subheader("Feature Gap Opportunities")
        if report.gap_opportunities:
            st.dataframe(report.gap_opportunities, hide_index=True, use_container_width=True)
        else:
            st.write("No gap opportunities identified.")

        for competitor in report.competitors:
            with st.expander(f"Competitor detail — {competitor.product_id}"):
                st.write(f"Total reviews: {competitor.total_reviews}")
                st.write(f"Sentiment: {competitor.sentiment_counts}")
                for point in competitor.pain_points:
                    st.write(f"{point['rank']}. {point['pain_point']} — {point['description']}")

st.subheader("Export")
pdf_bytes = generate_pdf_report(report)
st.download_button(
    "📄 Generate Report (PDF)",
    data=pdf_bytes,
    file_name=f"{main.product_id}_reviewpulse_report.pdf",
    mime="application/pdf",
    type="primary",
)
