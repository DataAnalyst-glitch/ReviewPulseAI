"""
Free, local embedding model — no API key, no rate limits, no per-call cost.
Chosen over the Gemini embedding API since Gemini setup is deferred and this
keeps Module 2 working today (brief's "reliable default path" philosophy).
"""

from langchain_huggingface import HuggingFaceEmbeddings

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_embedding_function: HuggingFaceEmbeddings | None = None


def get_embedding_function() -> HuggingFaceEmbeddings:
    global _embedding_function
    if _embedding_function is None:
        _embedding_function = HuggingFaceEmbeddings(model_name=MODEL_NAME)
    return _embedding_function
