"""
Basic logging (brief Section 5.8): not built for scale, just enough that a
failed demo mid-client-call can be diagnosed from logs/app.log in under a
minute, instead of only a stack trace on screen.
"""

import logging
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_FILE = LOG_DIR / "app.log"

_configured = False


def get_logger(name: str) -> logging.Logger:
    global _configured
    if not _configured:
        LOG_DIR.mkdir(exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[
                logging.FileHandler(LOG_FILE, encoding="utf-8"),
                logging.StreamHandler(),
            ],
        )
        _configured = True
    return logging.getLogger(name)
