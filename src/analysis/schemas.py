"""
Structured output schemas for Module 3's three agents. Each LLM call is
forced into one of these shapes via LangChain's with_structured_output(),
so results are parsed JSON, never free-text to regex out.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class SentimentResult(BaseModel):
    review_id: str
    sentiment: str = Field(description="One of: Positive, Neutral, Negative")


class SentimentBatch(BaseModel):
    results: List[SentimentResult]


class PainPoint(BaseModel):
    rank: int = Field(description="1, 2, or 3 — most recurring first")
    pain_point: str = Field(description="Short label, e.g. 'Short battery life'")
    description: str = Field(description="1-2 sentence summary of the complaint pattern")
    supporting_review_ids: List[str] = Field(description="review_id values that mention this issue")
    supporting_quotes: List[str] = Field(
        description="Exact verbatim short quotes copied from the review text supporting this claim — do not paraphrase these."
    )
    # Filled in by the guardrail after parsing, not by the LLM.
    verified_quote_count: int = 0
    needs_manual_review: bool = False


class PainPointBatch(BaseModel):
    pain_points: List[PainPoint]


class GapOpportunity(BaseModel):
    competitor_product_id: str
    competitor_pain_point: str = Field(description="The competitor pain point this opportunity is based on")
    opportunity: str = Field(description="The feature-gap opportunity for the seller, in plain English")
    rationale: str = Field(description="Why this is a gap: not a comparable pain point for the seller's own product")


class GapOpportunityBatch(BaseModel):
    opportunities: List[GapOpportunity]


class LLMUsage(BaseModel):
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
