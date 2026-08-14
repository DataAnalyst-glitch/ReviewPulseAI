"""
Gemini LLM access for Module 3. Uses the "gemini-flash-lite-latest" alias
rather than pinning a dated model id — Gemini deprecates specific model
versions for new API keys fairly often (gemini-2.5-flash and
gemini-2.5-flash-lite both returned 404 "no longer available to new
users" when tested here), and the alias is Google's own mechanism for
avoiding that. Flash-Lite over plain Flash deliberately: "gemini-flash-latest"
resolved to a reasoning/"thinking" model (gemini-3.7-flash) with only a
20-requests/day free-tier quota, which real analysis runs (multiple calls
per product) burn through almost immediately — not viable for a live
client demo. Flash-Lite has no reasoning overhead (near-zero output
tokens on a trivial prompt vs. ~90% reasoning tokens on flash-latest) and
this task (classification + short structured extraction) doesn't need
that reasoning depth anyway.
"""

import os

from langchain_google_genai import ChatGoogleGenerativeAI

MODEL_NAME = "gemini-flash-lite-latest"

_llm: ChatGoogleGenerativeAI | None = None


def get_llm() -> ChatGoogleGenerativeAI:
    global _llm
    if _llm is None:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")
        _llm = ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=api_key, temperature=0.2)
    return _llm
