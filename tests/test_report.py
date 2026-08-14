import io

import pytest

from src.analysis.schemas import GapOpportunity, GapOpportunityBatch, PainPoint, SentimentBatch, SentimentResult
from src.analysis.storage import save_gap_opportunities, save_pain_points, save_sentiment_results
from src.ingestion.schema import Review
from src.report import ComparisonReport, ProductReport, build_comparison_report, build_product_report, disclaimer_text
from src.report.pdf_generator import generate_pdf_report
from src.report.voice_summary import build_voice_summary


def _seed(monkeypatch, tmp_path):
    import src.analysis.storage as storage_module

    monkeypatch.setattr(storage_module, "DB_PATH", tmp_path / "test.db")

    main_reviews = [
        Review(product_id="MAIN", review_text="Battery dies fast, very disappointing.", rating=2.0, is_demo_data=True),
        Review(product_id="MAIN", review_text="Sound quality is excellent for the price.", rating=5.0, is_demo_data=True),
    ]
    save_sentiment_results(
        "MAIN",
        SentimentBatch(
            results=[
                SentimentResult(review_id=main_reviews[0].review_id, sentiment="Negative"),
                SentimentResult(review_id=main_reviews[1].review_id, sentiment="Positive"),
            ]
        ),
        main_reviews,
    )
    save_pain_points(
        "MAIN",
        [
            PainPoint(
                rank=1,
                pain_point="Battery life",
                description="Battery drains quickly",
                supporting_review_ids=[main_reviews[0].review_id],
                supporting_quotes=["Battery dies fast"],
                verified_quote_count=1,
                needs_manual_review=False,
                recommended_action="Add a battery-life disclaimer to bullet #3 and test a larger-capacity cell.",
                suggested_listing_copy="LONG-LASTING POWER - Upgraded cell keeps you listening all day on a single charge.",
            )
        ],
    )

    comp_reviews = [Review(product_id="COMP", review_text="Ear tips fall out constantly.", rating=2.0)]
    save_sentiment_results(
        "COMP",
        SentimentBatch(results=[SentimentResult(review_id=comp_reviews[0].review_id, sentiment="Negative")]),
        comp_reviews,
    )
    save_pain_points(
        "COMP",
        [
            PainPoint(
                rank=1,
                pain_point="Fit",
                description="Ear tips too large",
                supporting_review_ids=[comp_reviews[0].review_id],
                supporting_quotes=["fall out constantly"],
                verified_quote_count=1,
                needs_manual_review=False,
            )
        ],
    )

    save_gap_opportunities(
        "MAIN",
        GapOpportunityBatch(
            opportunities=[
                GapOpportunity(
                    competitor_product_id="COMP",
                    competitor_pain_point="Fit",
                    opportunity="Highlight secure, comfortable fit",
                    rationale="MAIN has no fit complaints",
                    recommended_action="Add 'secure all-day fit' to the main image callouts.",
                )
            ]
        ),
    )


def test_build_product_report(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)

    report = build_product_report("MAIN")

    assert isinstance(report, ProductReport)
    assert report.product_id == "MAIN"
    assert report.is_demo_data is True
    assert report.total_reviews == 2
    assert report.sentiment_counts == {"Negative": 1, "Positive": 1}
    assert len(report.pain_points) == 1
    assert report.pain_points[0]["pain_point"] == "Battery life"


def test_build_comparison_report(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)

    report = build_comparison_report("MAIN", ["COMP"])

    assert isinstance(report, ComparisonReport)
    assert report.main.product_id == "MAIN"
    assert len(report.competitors) == 1
    assert report.competitors[0].product_id == "COMP"
    assert len(report.gap_opportunities) == 1
    assert report.gap_opportunities[0]["competitor_product_id"] == "COMP"


def test_generate_pdf_report_produces_valid_pdf_bytes(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    report = build_comparison_report("MAIN", ["COMP"])

    pdf_bytes = generate_pdf_report(report)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_generate_pdf_report_renders_recommendations(monkeypatch, tmp_path):
    # fpdf2 compresses content streams by default, so a raw byte-substring
    # check on the output would silently pass/fail regardless of what's
    # actually rendered — extract real text via pypdf instead.
    pypdf = pytest.importorskip("pypdf")

    _seed(monkeypatch, tmp_path)
    report = build_comparison_report("MAIN", ["COMP"])

    pdf_bytes = generate_pdf_report(report)
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() for page in reader.pages)

    assert "Recommended action" in text
    assert "battery-life disclaimer" in text
    assert "main image callouts" in text
    assert "Suggested Listing Copy" in text
    assert "LONG-LASTING POWER" in text
    # Fallback text version of the voice summary (Update Brief Addition 2)
    # must be in the PDF too — the report can't depend on audio playback.
    # (Substrings, not an exact match: multi_cell line-wraps long text with
    # its own newlines, which won't match pypdf's extracted line breaks.)
    assert "Executive Summary" in text
    assert "quick summary for MAIN" in text
    assert "50 percent positive, 50 percent negative" in text
    # Trust/accuracy disclaimer must appear on every page's footer.
    assert "customer review text only" in text
    assert "does not incorporate sales volume, pricing, or market trend data" in text


def test_disclaimer_text_includes_review_count():
    text = disclaimer_text(42)

    assert "42 reviews analyzed" in text
    assert "sales volume, pricing, or market trend data" in text
    assert "business judgment" in text


def test_generate_pdf_report_handles_no_competitors(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    report = build_comparison_report("MAIN", [])

    pdf_bytes = generate_pdf_report(report)

    assert pdf_bytes.startswith(b"%PDF")


def _make_report(sentiment_counts, pain_points, total_reviews=None):
    main = ProductReport(
        product_id="MAIN",
        is_demo_data=False,
        total_reviews=total_reviews if total_reviews is not None else sum(sentiment_counts.values()),
        sentiment_counts=sentiment_counts,
        pain_points=pain_points,
    )
    return ComparisonReport(main=main, competitors=[], gap_opportunities=[])


def test_build_voice_summary_includes_sentiment_and_top_pain_point():
    report = _make_report(
        {"Positive": 6, "Neutral": 1, "Negative": 8},
        [
            {
                "rank": 1,
                "pain_point": "Short battery life",
                "recommended_action": "Update bullet #3 to set expectations honestly.",
            }
        ],
    )

    summary = build_voice_summary(report)

    assert "MAIN" in summary
    assert "15 reviews" in summary
    assert "40 percent positive" in summary
    assert "53 percent negative" in summary
    assert "Short battery life" in summary
    assert "Update bullet #3" in summary


def test_build_voice_summary_omits_insufficient_data_fallback():
    report = _make_report(
        {"Positive": 1, "Negative": 1},
        [{"rank": 1, "pain_point": "Vague issue", "recommended_action": "Insufficient data for a specific recommendation."}],
    )

    summary = build_voice_summary(report)

    assert "Vague issue" in summary
    assert "Insufficient data" not in summary


def test_build_voice_summary_handles_no_pain_points():
    report = _make_report({"Positive": 2}, [])

    summary = build_voice_summary(report)

    assert "No major pain points" in summary


def test_build_voice_summary_handles_zero_reviews():
    report = _make_report({}, [], total_reviews=0)

    summary = build_voice_summary(report)

    assert "No reviews were available" in summary
