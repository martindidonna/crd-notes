from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from crd_notes.core.paths import DATA_DIR


def configure_logging() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    if logger.handlers:
        return

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        DATA_DIR / "crd-notes.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console)
    logger.addHandler(file_handler)
