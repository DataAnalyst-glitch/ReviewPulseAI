"""
Chunk cleaned reviews into LangChain Documents for embedding.

Most reviews are a sentence or two and won't actually split, but the
splitter still runs so longer reviews are handled correctly. Each chunk's
metadata carries the full original review text — the pain-point agent in
Module 3 needs to quote/paraphrase the exact source text as a guardrail
against hallucination (brief Section 5.4), so that traceability has to
survive the chunking step.
"""

from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.ingestion.schema import Review

CHUNK_SIZE = 300
CHUNK_OVERLAP = 40


def chunk_reviews(reviews: List[Review]) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    documents: List[Document] = []

    for review in reviews:
        chunks = splitter.split_text(review.review_text)
        for index, chunk_text in enumerate(chunks):
            metadata = {
                "review_id": review.review_id,
                "product_id": review.product_id,
                "chunk_index": index,
                "rating": review.rating,
                "review_date": review.review_date,
                "verified_purchase": review.verified_purchase,
                "source": review.source,
                "is_demo_data": review.is_demo_data,
                "original_review_text": review.review_text,
            }
            # Chroma rejects None metadata values, so drop any unset optional fields.
            metadata = {k: v for k, v in metadata.items() if v is not None}
            documents.append(Document(page_content=chunk_text, metadata=metadata))

    return documents
