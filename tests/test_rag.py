from src.ingestion.csv_loader import load_reviews_from_csv
from src.rag.chunking import chunk_reviews
from src.rag.vector_store import add_new_documents, get_vector_store, search_reviews
from tests.test_ingestion import SAMPLE_DIR


def _load_sample_reviews(product_id: str):
    return load_reviews_from_csv(str(SAMPLE_DIR / f"{product_id}.csv"), product_id=product_id)


def test_chunk_reviews_preserves_traceable_metadata():
    reviews = _load_sample_reviews("DEMO-EARBUDS-A")
    documents = chunk_reviews(reviews)

    assert len(documents) >= len(reviews)  # at least one chunk per review
    for doc in documents:
        assert doc.metadata["product_id"] == "DEMO-EARBUDS-A"
        assert doc.metadata["review_id"]
        assert doc.metadata["original_review_text"]  # needed for Module 3 citation guardrail
        assert "reviewer_name" not in doc.metadata
        assert None not in doc.metadata.values()


def test_index_and_search_isolated_by_product(tmp_path):
    reviews_a = _load_sample_reviews("DEMO-EARBUDS-A")
    reviews_b = _load_sample_reviews("DEMO-EARBUDS-B")

    store = get_vector_store(persist_directory=str(tmp_path))
    added_a = add_new_documents(store, chunk_reviews(reviews_a))
    added_b = add_new_documents(store, chunk_reviews(reviews_b))
    assert added_a > 0
    assert added_b > 0

    results = search_reviews("battery life problems", product_id="DEMO-EARBUDS-A", k=3, store=store)
    assert len(results) > 0
    assert all(r.metadata["product_id"] == "DEMO-EARBUDS-A" for r in results)


def test_reindexing_same_reviews_is_a_no_op(tmp_path):
    reviews = _load_sample_reviews("DEMO-EARBUDS-A")
    documents = chunk_reviews(reviews)

    store = get_vector_store(persist_directory=str(tmp_path))
    first_pass = add_new_documents(store, documents)
    second_pass = add_new_documents(store, documents)

    assert first_pass == len(documents)
    assert second_pass == 0
