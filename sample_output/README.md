# Sample Output

`DEMO-EARBUDS-A_sample_report.pdf` is a fully-run example of ReviewPulse AI's output — input product ID `DEMO-EARBUDS-A` (with `DEMO-EARBUDS-B` as a competitor) through the complete pipeline (ingest → RAG index → sentiment/pain-point/gap analysis → PDF export) to a finished report, generated via `app.py`'s "Generate Report" button.

**This is demo data** — `DEMO-EARBUDS-A` and `DEMO-EARBUDS-B` are the two synthetic sample products bundled in `data/sample_reviews/` (see `CLAUDE.md` Section 5.1), not live-scraped reviews. The PDF itself says so under each product's sentiment section.

To regenerate it after a code change:

```python
from src.report import build_comparison_report
from src.report.pdf_generator import generate_pdf_report

report = build_comparison_report("DEMO-EARBUDS-A", ["DEMO-EARBUDS-B"])
pdf_bytes = generate_pdf_report(report)
open("sample_output/DEMO-EARBUDS-A_sample_report.pdf", "wb").write(pdf_bytes)
```

(Requires `data/reviewpulse.db` to already have results for both products — run `analyze_product()` on each first, or just click through the Streamlit app once.)
