"""
Local Chroma vector store — stands in for Supabase pgvector until Supabase
is set up. Both are accessed as a LangChain vector store, so swapping the
backend later means changing get_vector_store() only; chunking.py and the
rest of Module 2/3 don't need to change.
"""

from pathlib import Path
from typing import List, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document

from src.rag.embeddings import get_embedding_function
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

PERSIST_DIR = Path(__file__).resolve().parents[2] / "data" / "vector_store"
COLLECTION_NAME = "reviews"


def get_vector_store(persist_directory: Optional[str] = None, collection_name: str = COLLECTION_NAME) -> Chroma:
    directory = Path(persist_directory) if persist_directory else PERSIST_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embedding_function(),
        persist_directory=str(directory),
    )


def _chunk_id(document: Document) -> str:
    return f"{document.metadata['review_id']}_{document.metadata['chunk_index']}"


def add_new_documents(store: Chroma, documents: List[Document]) -> int:
    """Add only documents not already present, so re-indexing the same reviews is a safe no-op."""
    if not documents:
        return 0

    ids = [_chunk_id(doc) for doc in documents]
    existing_ids = set(store.get(ids=ids).get("ids", []))
    new_docs, new_ids = [], []
    for doc, doc_id in zip(documents, ids):
        if doc_id not in existing_ids:
            new_docs.append(doc)
            new_ids.append(doc_id)

    if new_docs:
        store.add_documents(new_docs, ids=new_ids)

    return len(new_docs)


def add_documents(documents: List[Document]) -> int:
    store = get_vector_store()
    added = add_new_documents(store, documents)
    logger.info("Vector store: added %d new chunks (%d already indexed)", added, len(documents) - added)
    return added


def search_reviews(
    query: str, product_id: Optional[str] = None, k: int = 5, store: Optional[Chroma] = None
) -> List[Document]:
    store = store or get_vector_store()
    filter_dict = {"product_id": product_id} if product_id else None
    return store.similarity_search(query, k=k, filter=filter_dict)
