"""
Token usage logging (brief Section 5.3) — not for billing enforcement,
just so real per-report token cost is known before pricing a Fiverr gig.
Gemini's free tier costs $0, but token counts are what you'd multiply by
paid-tier pricing later if you outgrow it.
"""

from typing import Optional

from src.analysis.llm import MODEL_NAME
from src.analysis.storage import log_llm_usage
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def log_usage(agent_name: str, product_id: str, usage_metadata: Optional[dict]) -> None:
    if not usage_metadata:
        logger.warning("%s for %s returned no usage metadata — token count not logged.", agent_name, product_id)
        return

    input_tokens = usage_metadata.get("input_tokens")
    output_tokens = usage_metadata.get("output_tokens")
    total_tokens = usage_metadata.get("total_tokens")

    log_llm_usage(
        agent=agent_name,
        product_id=product_id,
        model=MODEL_NAME,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )
    logger.info(
        "%s for %s used %s input / %s output / %s total tokens",
        agent_name, product_id, input_tokens, output_tokens, total_tokens,
    )
