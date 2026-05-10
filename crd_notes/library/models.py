from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal


OperationKind = Literal["action", "decision", "risk", "question"]
OperationStatus = Literal["open", "done"]
OperationSource = Literal["summary", "ai", "manual"]
KnowledgeFileStatus = Literal["pending", "indexed", "failed"]
ChatMessageRole = Literal["user", "assistant"]


DEFAULT_WORKSPACE_ID = "default"


@dataclass(frozen=True)
class Workspace:
    id: str
    name: str
    description: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class LibraryEntry:
    id: str
    workspace_id: str
    title: str
    notes: str
    participants: list[str]
    source_filename: str
    audio_filename: str | None
    duration_seconds: float | None
    recorded_on: date | None
    created_at: datetime
    transcript: str


@dataclass(frozen=True)
class Summary:
    id: str
    entry_id: str
    provider: str
    model: str
    prompt_id: str
    content: str
    created_at: datetime


@dataclass(frozen=True)
class SummaryMetadata:
    summary_id: str
    entry_id: str
    tags: list[str]
    keywords: list[str]
    people: list[str]
    topics: list[str]
    context: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class OperationItem:
    id: str
    entry_id: str
    summary_id: str | None
    kind: OperationKind
    text: str
    owner: str
    due_date: date | None
    status: OperationStatus
    source: OperationSource
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Job:
    id: str
    status: str
    stage: str
    progress: int
    message: str
    error: str | None
    entry_id: str | None
    payload: dict
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class WorkspaceKnowledgeFile:
    id: str
    workspace_id: str
    original_name: str
    stored_path: str
    content_type: str
    extension: str
    size_bytes: int
    sha256: str
    status: KnowledgeFileStatus
    error: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ChatThread:
    id: str
    workspace_id: str
    title: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ChatMessage:
    id: str
    thread_id: str
    role: ChatMessageRole
    content: str
    provider: str
    model: str
    created_at: datetime


@dataclass(frozen=True)
class ChatMessageSource:
    id: str
    message_id: str
    entry_id: str
    entry_title: str
    doc_type: str
    source: str
    score: float
    snippet: str
    created_at: datetime
