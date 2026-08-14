"""
Shared review record shape for Module 1.

PII handling (brief Section 5.4): reviewer identity (username, profile URL,
author id) is deliberately not a field on this dataclass. Those columns are
dropped at CSV-read time in csv_loader.py, before a Review is ever built —
identifiable reviewer data never enters the pipeline in the first place.
"""

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class Review:
    product_id: str
    review_text: str
    rating: Optional[float] = None
    review_date: Optional[str] = None
    verified_purchase: Optional[bool] = None
    source: str = "csv"
    is_demo_data: bool = False

    def to_dict(self) -> dict:
        return asdict(self)
