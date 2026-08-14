"""
Module 2 — RAG / Vector Storage.

Entry points: index_reviews() and retrieve_relevant_chunks(). Currently
backed by a local Chroma store (data/vector_store/) rather than Supabase
pgvector — Supabase setup is deferred, and Chroma is a drop-in swap for it
later since both are accessed through the same LangChain vector-store
interface. Every failure here raises RAGError with a friendly message
rather than a raw stack trace, matching Module 1's error-handling pattern.
"""

from typing import List, Optional

from langchain_core.documents import Document

from src.ingestion.schema import Review
from src.rag.chunking import chunk_reviews
from src.rag.vector_store import add_documents, search_reviews
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class RAGError(Exception):
    """Raised when chunking/embedding/indexing fails. Callers should show this message, not a stack trace."""


def index_reviews(reviews: List[Review]) -> int:
    """Chunk reviews, embed them, and add them to the vector store. Returns count of newly indexed chunks."""
    if not reviews:
        logger.warning("index_reviews called with no reviews — nothing to index.")
        return 0

    try:
        documents = chunk_reviews(reviews)
        added = add_documents(documents)
    except Exception as exc:  # noqa: BLE001 — indexing failures must not crash the app
        logger.error("Indexing failed for %d reviews: %s", len(reviews), exc)
        raise RAGError(f"Could not index reviews into the vector store: {exc}") from exc

    logger.info("Indexed %d new chunks (%d total chunks) for %d reviews", added, len(documents), len(reviews))
    return added


def retrieve_relevant_chunks(query: str, product_id: Optional[str] = None, k: int = 5) -> List[Document]:
    """Return the top-k review chunks most relevant to `query`, optionally filtered to one product."""
    try:
        return search_reviews(query, product_id=product_id, k=k)
    except Exception as exc:  # noqa: BLE001
        logger.error("Retrieval failed for query %r: %s", query, exc)
        raise RAGError(f"Could not search the vector store: {exc}") from exc
