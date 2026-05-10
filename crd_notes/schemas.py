from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from crd_notes.core.config import AppSettings


class PromptItem(BaseModel):
    id: str
    title: str
    description: str


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


class WorkspaceCreateRequest(BaseModel):
    name: str
    description: str = ""


class JobCreateResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    id: str
    status: str
    stage: str
    progress: int
    message: str
    error: str | None = None
    entry_id: str | None = None
    created_at: datetime
    updated_at: datetime


class RecordingSourceResponse(BaseModel):
    id: str
    label: str


class RecordingSourcesResponse(BaseModel):
    microphones: list[RecordingSourceResponse]
    system: list[RecordingSourceResponse]
    window_supported: bool
    window_detail: str


class RecordingStartRequest(BaseModel):
    workspace_id: str = "default"
    title: str = "Registrazione"
    recorded_on: date | None = None
    notes: str = ""
    participants: list[str] = Field(default_factory=list)
    mode: Literal["microphone", "system", "microphone_system", "window"] = "microphone_system"
    microphone_device: str = ""
    system_device: str = "wasapi:default"
    window_hint: str = ""


class RecordingBookmarkCreateRequest(BaseModel):
    label: str = ""


class RecordingStopRequest(BaseModel):
    summarize: bool = False
    prompt_id: str = "riunione_tecnica"
    provider: str | None = None


class RecordingBookmarkResponse(BaseModel):
    id: str
    label: str
    timestamp_seconds: float
    created_at: datetime


class RecordingSessionResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    recorded_on: date | None = None
    notes: str
    participants: list[str]
    mode: str
    microphone_device: str
    system_device: str
    window_hint: str
    status: str
    elapsed_seconds: float
    bookmarks: list[RecordingBookmarkResponse]
    created_at: datetime
    updated_at: datetime
    error: str


class LibraryEntryListResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    notes: str
    participants: list[str]
    source_filename: str
    audio_filename: str | None
    duration_seconds: float | None
    recorded_on: date | None = None
    created_at: datetime
    summary_count: int = 0
    operation_open_count: int = 0
    operation_total_count: int = 0
    tags: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


class LibraryEntryDetailResponse(LibraryEntryListResponse):
    transcript: str


class SummaryResponse(BaseModel):
    id: str
    entry_id: str
    provider: str
    model: str
    prompt_id: str
    content: str
    created_at: datetime
    tags: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    context: str = ""


class LibraryDetailResponse(BaseModel):
    entry: LibraryEntryDetailResponse
    summaries: list[SummaryResponse]


class OperationEntryMeta(BaseModel):
    id: str
    workspace_id: str
    title: str
    recorded_on: date | None = None
    created_at: datetime


class OperationItemResponse(BaseModel):
    id: str
    entry_id: str
    summary_id: str | None = None
    kind: str
    text: str
    owner: str
    due_date: date | None = None
    status: str
    source: str
    created_at: datetime
    updated_at: datetime
    entry: OperationEntryMeta | None = None


class OperationItemUpdateRequest(BaseModel):
    text: str | None = None
    owner: str | None = None
    due_date: date | None = None
    status: str | None = None


class OperationExtractResponse(BaseModel):
    items: list[OperationItemResponse]


class IntelligenceItemResponse(BaseModel):
    text: str
    score: float
    count: int


class IntelligenceClusterResponse(BaseModel):
    id: str
    title: str
    terms: list[str]
    entry_ids: list[str]
    entry_titles: list[str]
    score: float


class IntelligenceTimelineItemResponse(BaseModel):
    text: str
    entry_id: str
    entry_title: str
    recorded_on: date | None = None
    created_at: datetime


class WorkspaceIntelligenceResponse(BaseModel):
    workspace_id: str
    generated_at: datetime
    entry_count: int
    summary_count: int
    operation_open_count: int
    top_tags: list[IntelligenceItemResponse]
    top_keywords: list[IntelligenceItemResponse]
    top_people: list[IntelligenceItemResponse]
    top_topics: list[IntelligenceItemResponse]
    clusters: list[IntelligenceClusterResponse]
    decisions: list[IntelligenceTimelineItemResponse]
    risks: list[IntelligenceTimelineItemResponse]
    questions: list[IntelligenceTimelineItemResponse]
    local_brief: str


class WorkspaceAiBriefRequest(BaseModel):
    provider: str | None = None
    model: str | None = None


class WorkspaceAiBriefResponse(BaseModel):
    brief: str


class ChatThreadResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatThreadCreateRequest(BaseModel):
    title: str = ""


class ChatThreadUpdateRequest(BaseModel):
    title: str


class ChatMessageSourceResponse(BaseModel):
    id: str
    message_id: str
    entry_id: str
    entry_title: str
    doc_type: str
    source: str
    score: float
    snippet: str
    created_at: datetime


class ChatMessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    provider: str
    model: str
    created_at: datetime
    sources: list[ChatMessageSourceResponse] = Field(default_factory=list)
    followups: list[str] = Field(default_factory=list)


class ChatThreadDetailResponse(BaseModel):
    thread: ChatThreadResponse
    messages: list[ChatMessageResponse]


class ChatMessageCreateRequest(BaseModel):
    content: str
    mentioned_entry_ids: list[str] = Field(default_factory=list)
    mentioned_knowledge_folders: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None


class ChatMessageCreateResponse(BaseModel):
    thread: ChatThreadResponse
    messages: list[ChatMessageResponse]


class WorkspaceKnowledgeFileResponse(BaseModel):
    id: str
    workspace_id: str
    original_name: str
    content_type: str
    extension: str
    size_bytes: int
    sha256: str
    status: str
    error: str
    created_at: datetime
    updated_at: datetime


class SettingsResponse(BaseModel):
    settings: AppSettings


class SummaryCreateRequest(BaseModel):
    prompt_id: str
    provider: str | None = None
    model: str | None = None
