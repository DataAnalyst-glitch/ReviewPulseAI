from src.analysis.schemas import GapOpportunity, GapOpportunityBatch, PainPoint, SentimentBatch, SentimentResult
from src.analysis.storage import save_gap_opportunities, save_pain_points, save_sentiment_results
from src.ingestion.schema import Review
from src.report import ComparisonReport, ProductReport, build_comparison_report, build_product_report
from src.report.pdf_generator import generate_pdf_report


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


def test_generate_pdf_report_handles_no_competitors(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    report = build_comparison_report("MAIN", [])

    pdf_bytes = generate_pdf_report(report)

    assert pdf_bytes.startswith(b"%PDF")
