from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from crd_notes.core.paths import CONFIG_PATH, ensure_data_dirs

ProviderName = Literal["openai", "openrouter", "ollama", "lmstudio", "copilot"]


class ProviderSettings(BaseModel):
    enabled: bool = False
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class RagSettings(BaseModel):
    enabled: bool = False
    storage_dir: str = "rag"
    collection_prefix: str = "workspace"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    chunk_size_words: int = Field(default=180, ge=40, le=500)
    chunk_overlap_words: int = Field(default=35, ge=0, le=499)
    top_k: int = Field(default=8, ge=1, le=50)
    candidate_k: int = Field(default=32, ge=1, le=200)
    max_context_chars: int = Field(default=3200, ge=500, le=50000)
    rerank_enabled: bool = True
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    hybrid_keyword_enabled: bool = True
    enrich_summaries: bool = True
    enrich_with_transcript_chunks: bool = True
    enrich_with_summary_chunks: bool = True
    enrich_with_metadata_chunks: bool = True
    enrich_with_operation_chunks: bool = True
    enrich_with_knowledge_chunks: bool = True

    @field_validator("chunk_overlap_words")
    @classmethod
    def overlap_must_be_smaller_than_chunk(cls, value: int, info) -> int:
        chunk_size = info.data.get("chunk_size_words", 180)
        if value >= chunk_size:
            raise ValueError("chunk_overlap_words deve essere minore di chunk_size_words")
        return value


class AppSettings(BaseModel):
    hardware_preset: str = "manual"
    detected_hardware: dict[str, Any] = Field(default_factory=dict)
    whisper_model: str = "base"
    transcription_language: str = "it"
    whisper_device: Literal["cpu", "cuda"] = "cpu"
    whisper_compute_type: str = "int8"
    whisper_beam_size: int = Field(default=1, ge=1, le=10)
    whisper_cpu_threads: int = Field(default=0, ge=0, le=64)
    whisper_workers: int = Field(default=1, ge=1, le=16)
    whisper_vad_filter: bool = True
    whisper_condition_on_previous_text: bool = False
    active_provider: ProviderName = "ollama"
    active_prompt: str = "riunione_tecnica"
    rag: RagSettings = Field(default_factory=RagSettings)
    providers: dict[ProviderName, ProviderSettings] = Field(
        default_factory=lambda: {
            "openai": ProviderSettings(
                base_url="https://api.openai.com/v1",
            ),
            "openrouter": ProviderSettings(
                base_url="https://openrouter.ai/api/v1",
            ),
            "ollama": ProviderSettings(
                base_url="http://127.0.0.1:11434",
            ),
            "lmstudio": ProviderSettings(
                base_url="http://127.0.0.1:1234/v1",
            ),
            "copilot": ProviderSettings(
                base_url="",
            ),
        }
    )


class SettingsStore:
    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self.path = path

    def load(self) -> AppSettings:
        ensure_data_dirs()
        if not self.path.exists():
            settings = AppSettings()
            self.save(settings)
            return settings

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return AppSettings.model_validate(raw)

    def save(self, settings: AppSettings) -> AppSettings:
        ensure_data_dirs()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        tmp_path.write_text(
            json.dumps(settings.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp_path, self.path)
        return settings
