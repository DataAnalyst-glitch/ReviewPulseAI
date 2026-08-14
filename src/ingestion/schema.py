"""
Shared review record shape for Module 1.

PII handling (brief Section 5.4): reviewer identity (username, profile URL,
author id) is deliberately not a field on this dataclass. Those columns are
dropped at CSV-read time in csv_loader.py, before a Review is ever built —
identifiable reviewer data never enters the pipeline in the first place.
"""

import hashlib
from dataclasses import asdict, dataclass, field
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
    review_id: str = field(default="")

    def __post_init__(self) -> None:
        if not self.review_id:
            # Stable across re-ingestion of the same review, so Module 2 chunk
            # ids (and later citation back to source review) stay consistent.
            digest = hashlib.sha1(f"{self.product_id}|{self.review_text}".encode("utf-8"))
            self.review_id = digest.hexdigest()[:16]

    def to_dict(self) -> dict:
        return asdict(self)
