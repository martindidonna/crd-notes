from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("CRD_NOTES_DATA_DIR", Path.cwd() / "data")).resolve()
INBOX_DIR = DATA_DIR / "inbox"
AUDIO_DIR = DATA_DIR / "audio"
RECORDINGS_DIR = DATA_DIR / "recordings"
RAG_DIR = DATA_DIR / "rag"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
DB_PATH = DATA_DIR / "crd_notes.sqlite3"
CONFIG_PATH = DATA_DIR / "config.json"
WEB_DIR = ROOT_DIR / "crd_notes" / "web"


def ensure_data_dirs() -> None:
    for path in (DATA_DIR, INBOX_DIR, AUDIO_DIR, RECORDINGS_DIR, RAG_DIR, KNOWLEDGE_DIR):
        path.mkdir(parents=True, exist_ok=True)
