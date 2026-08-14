"""
Module 4 — Streamlit presentation layer.

Keyword/ASIN → live competitor discovery isn't built (no such API is wired
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

COLOR_GOOD = "#0ca30c"
COLOR_CRITICAL = "#d03b3b"
COLOR_NEUTRAL = "#898781"
COLOR_SEQUENTIAL = "#2a78d6"
SENTIMENT_ORDER = ["Positive", "Neutral", "Negative"]
SENTIMENT_COLOR = {"Positive": COLOR_GOOD, "Neutral": COLOR_NEUTRAL, "Negative": COLOR_CRITICAL}

UPLOAD_DIR = Path("data") / "raw" / "uploads"

st.set_page_config(page_title="ReviewPulse AI", page_icon="📊", layout="wide")
st.title("ReviewPulse AI")
st.caption(
    "Enter a product ID and optionally upload a review CSV. Leave the CSV empty to fall back to a live API "
    "(if configured) or bundled demo data — the pipeline never breaks on a missing upload."
)


def _save_upload(uploaded_file, product_id: str) -> str | None:
    if uploaded_file is None:
        return None
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / f"{product_id}.csv"
    path.write_bytes(uploaded_file.getvalue())
    return str(path)


with st.form("analyze_form"):
    col_main, col_competitors = st.columns(2)

    with col_main:
        st.subheader("Your product")
        main_id = st.text_input("Product ID", value="DEMO-EARBUDS-A")
        main_csv = st.file_uploader("Reviews CSV (optional)", type="csv", key="main_csv")

    with col_competitors:
        st.subheader("Competitors (up to 3, optional)")
        competitor_inputs = []
        for i in range(3):
            default = "DEMO-EARBUDS-B" if i == 0 else ""
            cid = st.text_input(f"Competitor {i + 1} product ID", value=default, key=f"comp_id_{i}")
            ccsv = st.file_uploader(f"Competitor {i + 1} CSV (optional)", type="csv", key=f"comp_csv_{i}")
            competitor_inputs.append((cid.strip(), ccsv))

    submitted = st.form_submit_button("Analyze", type="primary")

if submitted:
    if not main_id.strip():
        st.error("Product ID is required.")
        st.stop()

    main_id = main_id.strip()
    competitors = [(cid, csv) for cid, csv in competitor_inputs if cid]

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

if "report" in st.session_state:
    report = st.session_state["report"]
    main = report.main

    if main.is_demo_data:
        st.info(f"**{main.product_id}** is bundled demo data — not live-scraped reviews.")

    st.header(f"Results — {main.product_id}")

    st.subheader("Sentiment Breakdown")
    col_chart, col_table = st.columns([2, 1])
    with col_chart:
        labels = [s for s in SENTIMENT_ORDER if main.sentiment_counts.get(s, 0) > 0]
        if labels:
            values = [main.sentiment_counts[s] for s in labels]
            colors = [SENTIMENT_COLOR[s] for s in labels]
            fig = go.Figure(data=[go.Pie(labels=labels, values=values, marker=dict(colors=colors), hole=0.4)])
            fig.update_traces(textinfo="label+percent", hovertemplate="%{label}: %{value} reviews<extra></extra>")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("No sentiment results.")
    with col_table:
        st.dataframe(
            {"Sentiment": SENTIMENT_ORDER, "Count": [main.sentiment_counts.get(s, 0) for s in SENTIMENT_ORDER]},
            hide_index=True,
        )

    st.subheader("Top Pain Points")
    if main.pain_points:
        pp_labels = [p["pain_point"] for p in main.pain_points]
        pp_counts = [len(p["supporting_review_ids"]) for p in main.pain_points]
        fig2 = go.Figure(data=[go.Bar(x=pp_counts, y=pp_labels, orientation="h", marker=dict(color=COLOR_SEQUENTIAL))])
        fig2.update_layout(yaxis=dict(autorange="reversed"), xaxis_title="Supporting reviews", height=250)
        st.plotly_chart(fig2, use_container_width=True)

        for point in main.pain_points:
            flag = "⚠️ needs manual review" if point["needs_manual_review"] else f"{point['verified_quote_count']} quote(s) verified"
            with st.expander(f"{point['rank']}. {point['pain_point']} — {flag}"):
                st.write(point["description"])
                for quote in point["supporting_quotes"]:
                    st.markdown(f"> {quote}")
    else:
        st.write("No pain points identified.")

    if report.competitors:
        st.subheader("Feature Gap Opportunities")
        if report.gap_opportunities:
            st.dataframe(report.gap_opportunities, hide_index=True)
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
        "Generate Report (PDF)",
        data=pdf_bytes,
        file_name=f"{main.product_id}_reviewpulse_report.pdf",
        mime="application/pdf",
    )
