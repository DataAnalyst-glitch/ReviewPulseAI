"""
Client-facing PDF export (brief Section 5.6) — turns a ComparisonReport into
a formatted PDF a seller can keep, forward, or show their team, without
needing to click into the live dashboard.

Colors are taken directly from the validated reference palette (dataviz
skill, references/palette.md) rather than picked by eye: sentiment uses the
fixed status roles (good/critical + a neutral gray, never re-themed), pain
points use the single default sequential hue (blue) since they're a
magnitude encoding, not an identity one.
"""

from datetime import datetime, timezone
from typing import Tuple

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from src.report import ComparisonReport, ProductReport

COLOR_GOOD = (12, 163, 12)  # status: good — #0ca30c
COLOR_CRITICAL = (208, 59, 59)  # status: critical — #d03b3b
COLOR_NEUTRAL = (137, 135, 129)  # muted ink — #898781
COLOR_SEQUENTIAL = (42, 120, 214)  # sequential hue, step 450 — #2a78d6
COLOR_PRIMARY_INK = (11, 11, 11)
COLOR_SECONDARY_INK = (82, 81, 78)
COLOR_TRACK = (225, 224, 217)  # gridline hairline, used as bar background track

SENTIMENT_ORDER = ["Positive", "Neutral", "Negative"]
SENTIMENT_COLOR = {"Positive": COLOR_GOOD, "Neutral": COLOR_NEUTRAL, "Negative": COLOR_CRITICAL}

PAGE_WIDTH_MM = 210
MARGIN_MM = 15
CONTENT_WIDTH_MM = PAGE_WIDTH_MM - 2 * MARGIN_MM


class ReportPDF(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*COLOR_PRIMARY_INK)
        self.cell(0, 10, "ReviewPulse AI - Review Analysis Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.set_draw_color(*COLOR_TRACK)
        self.line(MARGIN_MM, self.get_y(), PAGE_WIDTH_MM - MARGIN_MM, self.get_y())
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*COLOR_SECONDARY_INK)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def _section_title(pdf: FPDF, title: str) -> None:
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*COLOR_PRIMARY_INK)
    pdf.cell(0, 8, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*COLOR_SECONDARY_INK)


def _bar(pdf: FPDF, label: str, value: int, total: int, color: Tuple[int, int, int]) -> None:
    pct = (value / total * 100) if total else 0
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*COLOR_PRIMARY_INK)
    pdf.cell(35, 6, label, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_text_color(*COLOR_SECONDARY_INK)
    pdf.cell(30, 6, f"{value} ({pct:.0f}%)", new_x=XPos.RIGHT, new_y=YPos.TOP)

    bar_x, bar_y = pdf.get_x(), pdf.get_y() + 1
    bar_width = 80
    pdf.set_fill_color(*COLOR_TRACK)
    pdf.rect(bar_x, bar_y, bar_width, 4, style="F")
    pdf.set_fill_color(*color)
    pdf.rect(bar_x, bar_y, bar_width * (pct / 100), 4, style="F")
    pdf.ln(7)


def _sentiment_section(pdf: FPDF, report: ProductReport) -> None:
    _section_title(pdf, f"Sentiment Breakdown - {report.product_id}")
    if report.is_demo_data:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*COLOR_SECONDARY_INK)
        pdf.cell(0, 6, "Demo data - for illustration only, not live-scraped reviews.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for sentiment in SENTIMENT_ORDER:
        count = report.sentiment_counts.get(sentiment, 0)
        _bar(pdf, sentiment, count, report.total_reviews, SENTIMENT_COLOR[sentiment])


def _pain_points_section(pdf: FPDF, report: ProductReport) -> None:
    _section_title(pdf, f"Top Customer Pain Points - {report.product_id}")
    if not report.pain_points:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 6, "No pain points identified.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        return

    max_count = max((len(p["supporting_review_ids"]) for p in report.pain_points), default=1) or 1
    for point in report.pain_points:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*COLOR_PRIMARY_INK)
        review_count = len(point["supporting_review_ids"])
        pdf.cell(0, 7, f"{point['rank']}. {point['pain_point']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        bar_x, bar_y = pdf.get_x() + 5, pdf.get_y() + 1
        bar_width = 60
        pdf.set_fill_color(*COLOR_TRACK)
        pdf.rect(bar_x, bar_y, bar_width, 3, style="F")
        pdf.set_fill_color(*COLOR_SEQUENTIAL)
        pdf.rect(bar_x, bar_y, bar_width * (review_count / max_count), 3, style="F")
        pdf.ln(5)

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*COLOR_SECONDARY_INK)
        pdf.set_x(MARGIN_MM + 5)
        pdf.multi_cell(CONTENT_WIDTH_MM - 5, 6, point["description"])

        if not point["needs_manual_review"] and point["supporting_quotes"]:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_x(MARGIN_MM + 5)
            pdf.multi_cell(CONTENT_WIDTH_MM - 5, 5, f'"{point["supporting_quotes"][0]}"')
        elif point["needs_manual_review"]:
            pdf.set_font("Helvetica", "BI", 9)
            pdf.set_text_color(*COLOR_CRITICAL)
            pdf.set_x(MARGIN_MM + 5)
            pdf.cell(0, 5, "Flagged for manual review - supporting quotes unverified.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if point.get("recommended_action"):
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*COLOR_SEQUENTIAL)
            pdf.set_x(MARGIN_MM + 5)
            pdf.write(5, "Recommended action: ")
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*COLOR_SECONDARY_INK)
            pdf.write(5, point["recommended_action"])
            pdf.ln(7)

        pdf.ln(3)


def _gap_opportunities_section(pdf: FPDF, report: ComparisonReport) -> None:
    _section_title(pdf, "Feature Gap Opportunities")
    if not report.gap_opportunities:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(*COLOR_SECONDARY_INK)
        pdf.cell(0, 6, "No gap opportunities identified.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        return

    for gap in report.gap_opportunities:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*COLOR_PRIMARY_INK)
        pdf.multi_cell(CONTENT_WIDTH_MM, 6, f"vs {gap['competitor_product_id']}: {gap['opportunity']}")

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*COLOR_SECONDARY_INK)
        pdf.set_x(MARGIN_MM + 5)
        pdf.multi_cell(CONTENT_WIDTH_MM - 5, 5, f"Competitor pain point: {gap['competitor_pain_point']}")
        pdf.set_x(MARGIN_MM + 5)
        pdf.multi_cell(CONTENT_WIDTH_MM - 5, 5, f"Why this works: {gap['rationale']}")

        if gap.get("recommended_action"):
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*COLOR_SEQUENTIAL)
            pdf.set_x(MARGIN_MM + 5)
            pdf.write(5, "Recommended action: ")
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*COLOR_SECONDARY_INK)
            pdf.write(5, gap["recommended_action"])
            pdf.ln(7)

        pdf.ln(3)


def generate_pdf_report(report: ComparisonReport) -> bytes:
    pdf = ReportPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(MARGIN_MM, MARGIN_MM, MARGIN_MM)
    pdf.add_page()

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*COLOR_SECONDARY_INK)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf.cell(0, 6, f"Generated {generated}  |  {report.main.total_reviews} reviews analyzed", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    _sentiment_section(pdf, report.main)
    _pain_points_section(pdf, report.main)

    for competitor in report.competitors:
        pdf.add_page()
        _sentiment_section(pdf, competitor)
        _pain_points_section(pdf, competitor)

    if report.competitors:
        pdf.add_page()
        _gap_opportunities_section(pdf, report)

    return bytes(pdf.output())
