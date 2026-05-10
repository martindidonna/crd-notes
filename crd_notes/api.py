from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from threading import Lock, Thread
from time import time
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from crd_notes.ai.connectors.copilot import CopilotConnector
from crd_notes.ai.prompts import get_prompts
from crd_notes.ai.service import AiService
from crd_notes.chat import WorkspaceChatService
from crd_notes.core.config import AppSettings, ProviderName, ProviderSettings, SettingsStore
from crd_notes.core.errors import CrdNotesError, LibraryError
from crd_notes.core.paths import INBOX_DIR, KNOWLEDGE_DIR, ROOT_DIR
from crd_notes.jobs import JobRunner
from crd_notes.knowledge import SUPPORTED_KNOWLEDGE_EXTENSIONS
from crd_notes.library.models import (
    ChatMessage,
    ChatMessageSource,
    ChatThread,
    DEFAULT_WORKSPACE_ID,
    Job,
    LibraryEntry,
    OperationItem,
    Summary,
    Workspace,
    WorkspaceKnowledgeFile,
)
from crd_notes.library.operations import AI_EXTRACTION_PROMPT, OperationService
from crd_notes.library.repository import LibraryRepository
from crd_notes.library.service import LibraryService
from crd_notes.library.summary_workflow import SummaryWorkflowService
from crd_notes.library.workspace_intelligence import (
    WORKSPACE_BRIEF_PROMPT,
    WorkspaceIntelligence,
    WorkspaceIntelligenceService,
    build_workspace_brief_input,
)
from crd_notes.rag import RagService
from crd_notes.recording import RecordingService
from crd_notes.schemas import (
    ChatMessageCreateRequest,
    ChatMessageCreateResponse,
    ChatMessageResponse,
    ChatMessageSourceResponse,
    ChatThreadCreateRequest,
    ChatThreadDetailResponse,
    ChatThreadResponse,
    ChatThreadUpdateRequest,
    IntelligenceClusterResponse,
    IntelligenceItemResponse,
    IntelligenceTimelineItemResponse,
    JobCreateResponse,
    JobStatusResponse,
    LibraryDetailResponse,
    LibraryEntryDetailResponse,
    LibraryEntryListResponse,
    OperationEntryMeta,
    OperationExtractResponse,
    OperationItemResponse,
    OperationItemUpdateRequest,
    PromptItem,
    RecordingBookmarkCreateRequest,
    RecordingBookmarkResponse,
    RecordingSessionResponse,
    RecordingSourcesResponse,
    RecordingStartRequest,
    RecordingStopRequest,
    SettingsResponse,
    SummaryCreateRequest,
    SummaryResponse,
    WorkspaceCreateRequest,
    WorkspaceAiBriefRequest,
    WorkspaceAiBriefResponse,
    WorkspaceKnowledgeFileResponse,
    WorkspaceIntelligenceResponse,
    WorkspaceResponse,
)


router = APIRouter(prefix="/api")

ALLOWED_UPLOAD_MIME_PREFIXES = ("audio/", "video/")
ALLOWED_UPLOAD_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".avi",
    ".flac",
    ".m4a",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".oga",
    ".ogg",
    ".ogv",
    ".opus",
    ".ts",
    ".wav",
    ".webm",
    ".wma",
    ".wmv",
}
MAX_KNOWLEDGE_UPLOAD_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_MEDIA_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024

_COPILOT_LOGIN_STATE: dict[str, object] = {
    "running": False,
    "completed": False,
    "success": False,
    "message": "",
    "verification_uri": "",
    "user_code": "",
    "updated_at": 0.0,
}
_COPILOT_LOGIN_LOCK = Lock()


def _update_copilot_login_state(**kwargs: object) -> None:
    with _COPILOT_LOGIN_LOCK:
        _COPILOT_LOGIN_STATE.update(kwargs)
        _COPILOT_LOGIN_STATE["updated_at"] = time()


def _read_copilot_login_state() -> dict[str, object]:
    with _COPILOT_LOGIN_LOCK:
        return dict(_COPILOT_LOGIN_STATE)


def _watch_copilot_login_process(process: subprocess.Popen[str]) -> None:
    message = "Login Copilot in corso. Completa l'autorizzazione su GitHub."
    verification_uri = ""
    user_code = ""
    if process.stdout is not None:
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            if "http" in lowered and "github" in lowered:
                verification_uri = line
            if "code" in lowered and any(char.isdigit() for char in line):
                user_code = line
            message = line
            _update_copilot_login_state(
                running=True,
                completed=False,
                success=False,
                message=message,
                verification_uri=verification_uri,
                user_code=user_code,
            )

    return_code = process.wait()
    if return_code == 0:
        _update_copilot_login_state(
            running=False,
            completed=True,
            success=True,
            message="Login Copilot completato. Ora puoi testare i modelli.",
        )
    else:
        final_message = message or "Login Copilot non riuscito."
        _update_copilot_login_state(
            running=False,
            completed=True,
            success=False,
            message=final_message,
        )


def get_repository() -> LibraryRepository:
    from crd_notes.app_state import repository

    return repository


def get_library_service() -> LibraryService:
    from crd_notes.app_state import library_service

    return library_service


def get_operation_service() -> OperationService:
    from crd_notes.app_state import operation_service

    return operation_service


def get_workspace_intelligence_service() -> WorkspaceIntelligenceService:
    from crd_notes.app_state import workspace_intelligence_service

    return workspace_intelligence_service


def get_settings_store() -> SettingsStore:
    from crd_notes.app_state import settings_store

    return settings_store


def get_job_runner() -> JobRunner:
    from crd_notes.app_state import job_runner

    return job_runner


def get_recording_service() -> RecordingService:
    from crd_notes.app_state import recording_service

    return recording_service


def get_ai_service() -> AiService:
    from crd_notes.app_state import ai_service

    return ai_service


def get_rag_service() -> RagService:
    from crd_notes.app_state import rag_service

    return rag_service


def get_summary_workflow_service() -> SummaryWorkflowService:
    from crd_notes.app_state import summary_workflow_service

    return summary_workflow_service


def reindex_entry_if_enabled(
    *,
    settings_store: SettingsStore,
    rag_service: RagService,
    entry_id: str,
) -> None:
    if not hasattr(settings_store, "load"):
        return
    if not hasattr(rag_service, "index_entry"):
        return
    settings = settings_store.load()
    if not settings.rag.enabled:
        return
    try:
        rag_service.index_entry(entry_id, settings)
    except CrdNotesError:
        return


def get_workspace_chat_service() -> WorkspaceChatService:
    from crd_notes.app_state import workspace_chat_service

    return workspace_chat_service


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": "crd-notes"}


@router.get("/prompts", response_model=list[PromptItem])
def list_prompts() -> list[PromptItem]:
    prompts = get_prompts()
    return [
        PromptItem(id=item.id, title=item.title, description=item.description)
        for item in prompts.values()
    ]


@router.get("/workspaces", response_model=list[WorkspaceResponse])
def list_workspaces(
    repository: Annotated[LibraryRepository, Depends(get_repository)],
) -> list[WorkspaceResponse]:
    return [workspace_to_response(workspace) for workspace in repository.list_workspaces()]


@router.post("/workspaces", response_model=WorkspaceResponse)
def create_workspace(
    request: WorkspaceCreateRequest,
    library_service: Annotated[LibraryService, Depends(get_library_service)],
) -> WorkspaceResponse:
    return workspace_to_response(
        library_service.create_workspace(name=request.name, description=request.description)
    )


@router.get(
    "/workspaces/{workspace_id}/knowledge/files",
    response_model=list[WorkspaceKnowledgeFileResponse],
)
def list_workspace_knowledge_files(
    workspace_id: str,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
) -> list[WorkspaceKnowledgeFileResponse]:
    if not repository.get_workspace(workspace_id):
        raise LibraryError("Workspace non trovato.")
    files = repository.list_workspace_knowledge_files(workspace_id)
    return [_knowledge_to_response(item) for item in files]


@router.post(
    "/workspaces/{workspace_id}/knowledge/files",
    response_model=list[WorkspaceKnowledgeFileResponse],
)
async def upload_workspace_knowledge_file(
    workspace_id: str,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
    settings_store: Annotated[SettingsStore, Depends(get_settings_store)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
    files: Annotated[list[UploadFile] | None, File()] = None,
    file: Annotated[UploadFile | None, File()] = None,
    relative_paths: Annotated[list[str] | None, Form()] = None,
) -> list[WorkspaceKnowledgeFileResponse]:
    if not repository.get_workspace(workspace_id):
        raise LibraryError("Workspace non trovato.")
    upload_files = _collect_knowledge_uploads(files, file)
    resolved_paths = _resolve_knowledge_relative_paths(upload_files, relative_paths)
    settings = settings_store.load()
    responses: list[WorkspaceKnowledgeFileResponse] = []

    for upload_file, relative_path in zip(upload_files, resolved_paths):
        original_name = _normalize_knowledge_original_name(upload_file.filename, relative_path)
        if not _is_allowed_knowledge_upload(original_name):
            raise CrdNotesError(
                "Formato file non supportato.",
                detail="Carica file pdf, doc, docx, txt, md, xls, xlsx o csv.",
            )

        extension = Path(original_name).suffix.lower()
        storage_dir = _workspace_knowledge_dir(workspace_id)
        stored_name = f"{uuid.uuid4()}{extension or '.bin'}"
        stored_path = storage_dir / stored_name
        hasher = hashlib.sha256()
        size_bytes = 0

        with stored_path.open("wb") as target:
            while chunk := await upload_file.read(1024 * 1024):
                size_bytes += len(chunk)
                if size_bytes > MAX_KNOWLEDGE_UPLOAD_BYTES:
                    target.close()
                    stored_path.unlink(missing_ok=True)
                    raise CrdNotesError(
                        "File troppo grande.",
                        detail="Dimensione massima consentita: 25 MB per file.",
                    )
                hasher.update(chunk)
                target.write(chunk)

        file_hash = hasher.hexdigest()
        existing = repository.find_workspace_knowledge_file_by_hash(
            workspace_id=workspace_id,
            sha256=file_hash,
        )
        if existing:
            stored_path.unlink(missing_ok=True)
            responses.append(_knowledge_to_response(existing))
            continue

        now = datetime.now(timezone.utc)
        knowledge_file = WorkspaceKnowledgeFile(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            original_name=original_name,
            stored_path=str(stored_path),
            content_type=(upload_file.content_type or "application/octet-stream"),
            extension=extension,
            size_bytes=size_bytes,
            sha256=file_hash,
            status="pending",
            error="",
            created_at=now,
            updated_at=now,
        )
        repository.add_workspace_knowledge_file(knowledge_file)
        if settings.rag.enabled:
            rag_service.index_workspace_knowledge_file(knowledge_file.id, settings)

        refreshed = repository.get_workspace_knowledge_file(knowledge_file.id)
        responses.append(_knowledge_to_response(refreshed or knowledge_file))

    return responses


@router.post(
    "/workspaces/{workspace_id}/knowledge/reindex",
)
def reindex_workspace_knowledge(
    workspace_id: str,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
    settings_store: Annotated[SettingsStore, Depends(get_settings_store)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
) -> dict[str, str]:
    if not repository.get_workspace(workspace_id):
        raise LibraryError("Workspace non trovato.")
    settings = settings_store.load()
    if settings.rag.enabled:
        rag_service.reindex_workspace(workspace_id, settings)
    return {"status": "ok"}


@router.post(
    "/workspaces/{workspace_id}/knowledge/files/{file_id}/reindex",
    response_model=WorkspaceKnowledgeFileResponse,
)
def reindex_workspace_knowledge_file(
    workspace_id: str,
    file_id: str,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
    settings_store: Annotated[SettingsStore, Depends(get_settings_store)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
) -> WorkspaceKnowledgeFileResponse:
    knowledge_file = repository.get_workspace_knowledge_file(file_id)
    if not knowledge_file or knowledge_file.workspace_id != workspace_id:
        raise LibraryError("File knowledge base non trovato.")
    settings = settings_store.load()
    if settings.rag.enabled:
        rag_service.index_workspace_knowledge_file(file_id, settings)
    refreshed = repository.get_workspace_knowledge_file(file_id)
    return _knowledge_to_response(refreshed or knowledge_file)


@router.delete(
    "/workspaces/{workspace_id}/knowledge/files/{file_id}",
    status_code=204,
)
def delete_workspace_knowledge_file(
    workspace_id: str,
    file_id: str,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
    settings_store: Annotated[SettingsStore, Depends(get_settings_store)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
) -> Response:
    knowledge_file = repository.get_workspace_knowledge_file(file_id)
    if not knowledge_file or knowledge_file.workspace_id != workspace_id:
        raise LibraryError("File knowledge base non trovato.")

    settings = settings_store.load()
    if settings.rag.enabled:
        rag_service.remove_workspace_knowledge_file(
            knowledge_file=knowledge_file,
            settings=settings,
        )
    repository.delete_workspace_knowledge_file(file_id)

    path = Path(knowledge_file.stored_path)
    if path.exists():
        path.unlink()
    return Response(status_code=204)


@router.get("/workspaces/{workspace_id}/intelligence", response_model=WorkspaceIntelligenceResponse)
def read_workspace_intelligence(
    workspace_id: str,
    service: Annotated[
        WorkspaceIntelligenceService, Depends(get_workspace_intelligence_service)
    ],
) -> WorkspaceIntelligenceResponse:
    return workspace_intelligence_to_response(service.build(workspace_id))


@router.post("/workspaces/{workspace_id}/intelligence/ai-brief", response_model=WorkspaceAiBriefResponse)
async def create_workspace_ai_brief(
    workspace_id: str,
    request: WorkspaceAiBriefRequest,
    service: Annotated[
        WorkspaceIntelligenceService, Depends(get_workspace_intelligence_service)
    ],
    settings_store: Annotated[SettingsStore, Depends(get_settings_store)],
    ai_service: Annotated[AiService, Depends(get_ai_service)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
) -> WorkspaceAiBriefResponse:
    settings = settings_store.load()
    intelligence = service.build(workspace_id)
    base_input = build_workspace_brief_input(intelligence)
    rag_context = rag_service.build_context(
        workspace_id=workspace_id,
        query_text=base_input,
        settings=settings,
        top_k=min(6, settings.rag.top_k),
    )
    result = await ai_service.complete_with_prompt(
        input_text=_append_rag_context(base_input, rag_context.context_text),
        system_prompt=WORKSPACE_BRIEF_PROMPT,
        settings=settings,
        provider=request.provider,
        model=request.model,
    )
    return WorkspaceAiBriefResponse(brief=result.content)


@router.get(
    "/workspaces/{workspace_id}/chat/threads",
    response_model=list[ChatThreadResponse],
)
def list_chat_threads(
    workspace_id: str,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
) -> list[ChatThreadResponse]:
    return [
        chat_thread_to_response(thread)
        for thread in repository.list_chat_threads(workspace_id or DEFAULT_WORKSPACE_ID)
    ]


@router.post(
    "/workspaces/{workspace_id}/chat/threads",
    response_model=ChatThreadResponse,
)
def create_chat_thread(
    workspace_id: str,
    request: ChatThreadCreateRequest,
    chat_service: Annotated[WorkspaceChatService, Depends(get_workspace_chat_service)],
) -> ChatThreadResponse:
    thread = chat_service.create_thread(
        workspace_id=workspace_id or DEFAULT_WORKSPACE_ID,
        title=request.title,
    )
    return chat_thread_to_response(thread)


@router.get(
    "/workspaces/{workspace_id}/chat/threads/{thread_id}",
    response_model=ChatThreadDetailResponse,
)
def read_chat_thread(
    workspace_id: str,
    thread_id: str,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
) -> ChatThreadDetailResponse:
    thread = repository.get_chat_thread(thread_id)
    if thread is None or thread.workspace_id != (workspace_id or DEFAULT_WORKSPACE_ID):
        raise HTTPException(status_code=404, detail="Chat non trovata.")
    sources = repository.list_chat_sources_for_thread(thread.id)
    return ChatThreadDetailResponse(
        thread=chat_thread_to_response(thread),
        messages=[
            chat_message_to_response(message, sources=sources.get(message.id, []))
            for message in repository.list_chat_messages(thread.id)
        ],
    )


@router.patch(
    "/workspaces/{workspace_id}/chat/threads/{thread_id}",
    response_model=ChatThreadResponse,
)
def update_chat_thread(
    workspace_id: str,
    thread_id: str,
    request: ChatThreadUpdateRequest,
    chat_service: Annotated[WorkspaceChatService, Depends(get_workspace_chat_service)],
) -> ChatThreadResponse:
    return chat_thread_to_response(
        chat_service.rename_thread(
            thread_id=thread_id,
            workspace_id=workspace_id or DEFAULT_WORKSPACE_ID,
            title=request.title,
        )
    )


@router.delete("/workspaces/{workspace_id}/chat/threads/{thread_id}")
def delete_chat_thread(
    workspace_id: str,
    thread_id: str,
    chat_service: Annotated[WorkspaceChatService, Depends(get_workspace_chat_service)],
) -> dict[str, bool]:
    chat_service.delete_thread(
        thread_id=thread_id,
        workspace_id=workspace_id or DEFAULT_WORKSPACE_ID,
    )
    return {"ok": True}


@router.post(
    "/workspaces/{workspace_id}/chat/threads/{thread_id}/messages",
    response_model=ChatMessageCreateResponse,
)
async def create_chat_message(
    workspace_id: str,
    thread_id: str,
    request: ChatMessageCreateRequest,
    settings_store: Annotated[SettingsStore, Depends(get_settings_store)],
    chat_service: Annotated[WorkspaceChatService, Depends(get_workspace_chat_service)],
) -> ChatMessageCreateResponse:
    turn = await chat_service.send_message(
        thread_id=None if thread_id == "new" else thread_id,
        workspace_id=workspace_id or DEFAULT_WORKSPACE_ID,
        content=request.content,
        mentioned_entry_ids=request.mentioned_entry_ids,
        mentioned_knowledge_folders=request.mentioned_knowledge_folders,
        settings=settings_store.load(),
        provider=request.provider if request.provider else None,
        model=request.model,
    )
    return ChatMessageCreateResponse(
        thread=chat_thread_to_response(turn.thread),
        messages=[
            chat_message_to_response(turn.user_message),
            chat_message_to_response(turn.assistant_message, sources=turn.sources),
        ],
    )


@router.get(
    "/workspaces/{workspace_id}/chat/mentions",
    response_model=list[LibraryEntryListResponse],
)
def list_chat_mentions(
    workspace_id: str,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
    q: str = "",
) -> list[LibraryEntryListResponse]:
    metadata = repository.entry_metadata()
    counts = repository.library_counts()
    return [
        entry_to_response(
            entry,
            counts=counts.get(entry.id, {}),
            metadata=metadata.get(entry.id, {}),
        )
        for entry in repository.list_entries(
            workspace_id or DEFAULT_WORKSPACE_ID,
            query=q,
            include_transcript=False,
        )[:8]
    ]


@router.get("/settings", response_model=SettingsResponse)
def read_settings(store: Annotated[SettingsStore, Depends(get_settings_store)]) -> SettingsResponse:
    return SettingsResponse(settings=store.load())


@router.put("/settings", response_model=SettingsResponse)
def update_settings(
    settings: AppSettings,
    store: Annotated[SettingsStore, Depends(get_settings_store)],
) -> SettingsResponse:
    return SettingsResponse(settings=store.save(settings))


@router.get("/providers/{provider}/models")
async def list_provider_models(
    provider: ProviderName,
    store: Annotated[SettingsStore, Depends(get_settings_store)],
) -> dict[str, object]:
    settings = store.load()
    provider_settings = settings.providers[provider]
    current = provider_settings.model

    try:
        if provider == "ollama":
            models = await _ollama_models(provider_settings.base_url)
        elif provider in {"openai", "openrouter", "lmstudio"}:
            models = await _openai_compatible_models(
                provider_settings.base_url,
                api_key=provider_settings.api_key,
                needs_key=provider in {"openai", "openrouter"},
            )
        elif provider == "copilot":
            data = await _copilot_model_status()
            models = data["models"]
        else:
            models = [current] if current else []
    except Exception as exc:
        models = [current] if current else []
        return {
            "provider": provider,
            "models": models,
            "source": "configured",
            "message": f"Modelli remoti non disponibili: {exc}",
        }

    if current and current not in models:
        models.insert(0, current)
    return {"provider": provider, "models": models, "source": "remote", "message": ""}


@router.post("/providers/{provider}/models/test")
async def test_provider_models(
    provider: ProviderName,
    provider_settings: ProviderSettings,
) -> dict[str, object]:
    try:
        if provider == "ollama":
            models = await _ollama_models(provider_settings.base_url)
        elif provider in {"openai", "openrouter", "lmstudio"}:
            models = await _openai_compatible_models(
                provider_settings.base_url,
                api_key=provider_settings.api_key,
                needs_key=provider in {"openai", "openrouter"},
            )
        elif provider == "copilot":
            data = await _copilot_model_status()
            models = data["models"]
            if not data.get("authenticated"):
                return {
                    "provider": provider,
                    "models": models,
                    "source": "error",
                    "message": "Accesso Copilot non trovato. Avvia il login Copilot, poi testa di nuovo i modelli.",
                }
            login = data.get("login") or "utente locale"
            return {
                "provider": provider,
                "models": models,
                "source": "remote",
                "message": f"Accesso Copilot valido per {login}. Trovati {len(models)} modelli.",
            }
        else:
            models = [provider_settings.model] if provider_settings.model else []
    except Exception as exc:
        return {
            "provider": provider,
            "models": [],
            "source": "error",
            "message": f"Test non riuscito: {exc}",
        }

    return {
        "provider": provider,
        "models": models,
        "source": "remote",
        "message": f"Trovati {len(models)} modelli.",
    }


@router.post("/providers/copilot/login")
def start_copilot_login() -> dict[str, str]:
    state = _read_copilot_login_state()
    if state.get("running"):
        return {"message": "Login Copilot gia' in corso. Completa la procedura aperta in app."}

    command = _copilot_login_command()
    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = subprocess.CREATE_NO_WINDOW
    process = subprocess.Popen(
        command,
        cwd=ROOT_DIR,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creationflags,
    )
    _update_copilot_login_state(
        running=True,
        completed=False,
        success=False,
        message="Login Copilot avviato. Attendi istruzioni di autorizzazione.",
        verification_uri="",
        user_code="",
    )
    Thread(target=_watch_copilot_login_process, args=(process,), daemon=True).start()

    return {
        "message": "Login Copilot avviato in app. Segui le istruzioni mostrate e attendi il completamento.",
    }


@router.get("/providers/copilot/login")
async def read_copilot_login_status() -> dict[str, object]:
    state = _read_copilot_login_state()
    if state.get("completed") and state.get("success"):
        try:
            data = await _copilot_model_status()
            models = data.get("models", [])
            login = data.get("login") or "utente locale"
            state["message"] = f"Accesso Copilot valido per {login}. Trovati {len(models)} modelli."
            state["models"] = models
        except Exception:
            state["models"] = []
    return state


async def _openai_compatible_models(
    base_url: str,
    *,
    api_key: str,
    needs_key: bool,
) -> list[str]:
    if needs_key and not api_key:
        raise ValueError("chiave API mancante")
    if not base_url:
        raise ValueError("URL base mancante")

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{base_url.rstrip('/')}/models", headers=headers)
        response.raise_for_status()
        data = response.json()

    models = [
        item.get("id")
        for item in data.get("data", [])
        if isinstance(item, dict) and item.get("id")
    ]
    return sorted(set(models))


async def _ollama_models(base_url: str) -> list[str]:
    if not base_url:
        raise ValueError("URL base mancante")
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{base_url.rstrip('/')}/api/tags")
        response.raise_for_status()
        data = response.json()
    return sorted(
        item["name"]
        for item in data.get("models", [])
        if isinstance(item, dict) and item.get("name")
    )


async def _copilot_model_status() -> dict[str, object]:
    data = await CopilotConnector().list_models()
    models = data.get("models", [])
    if not isinstance(models, list):
        raise ValueError("risposta modelli Copilot non valida")
    return {
        "models": [str(model) for model in models],
        "login": str(data.get("login") or ""),
        "auth_type": str(data.get("authType") or ""),
        "authenticated": bool(data.get("authenticated")),
    }


def _copilot_login_command() -> list[str]:
    if sys.platform.startswith("win"):
        local = ROOT_DIR / "node_modules" / ".bin" / "copilot.cmd"
    else:
        local = ROOT_DIR / "node_modules" / ".bin" / "copilot"
    executable = str(local) if local.exists() else "copilot"
    return [executable, "login"]


def _is_allowed_media_upload(filename: str | None, content_type: str | None) -> bool:
    normalized_type = (content_type or "").lower()
    if any(normalized_type.startswith(prefix) for prefix in ALLOWED_UPLOAD_MIME_PREFIXES):
        return True

    suffix = Path(filename or "").suffix.lower()
    return suffix in ALLOWED_UPLOAD_EXTENSIONS


def _max_media_upload_bytes() -> int:
    raw = os.environ.get("CRD_NOTES_MAX_MEDIA_UPLOAD_MB", "").strip()
    if not raw:
        return DEFAULT_MAX_MEDIA_UPLOAD_BYTES
    try:
        megabytes = int(raw)
    except ValueError:
        return DEFAULT_MAX_MEDIA_UPLOAD_BYTES
    return max(1, megabytes) * 1024 * 1024


def _is_allowed_knowledge_upload(filename: str | None) -> bool:
    suffix = Path(filename or "").suffix.lower()
    return suffix in SUPPORTED_KNOWLEDGE_EXTENSIONS


def _collect_knowledge_uploads(
    files: list[UploadFile] | None,
    file: UploadFile | None,
) -> list[UploadFile]:
    collected = [item for item in (files or []) if item is not None]
    if file is not None:
        collected.append(file)
    if not collected:
        raise CrdNotesError(
            "Nessun file selezionato.",
            detail="Seleziona almeno un file da caricare.",
        )
    return collected


def _resolve_knowledge_relative_paths(
    upload_files: list[UploadFile],
    relative_paths: list[str] | None,
) -> list[str | None]:
    if not relative_paths:
        return [None] * len(upload_files)
    if len(relative_paths) != len(upload_files):
        raise CrdNotesError(
            "Metadati upload non validi.",
            detail="Il numero dei percorsi relativi non corrisponde ai file caricati.",
        )
    return [item.strip() or None for item in relative_paths]


def _normalize_knowledge_original_name(
    filename: str | None,
    relative_path: str | None,
) -> str:
    raw = (relative_path or filename or "").strip()
    if not raw:
        raise CrdNotesError(
            "Nome file non valido.",
            detail="Ogni file deve avere un nome valido.",
        )

    normalized = raw.replace("\\", "/")
    path = PurePosixPath(normalized)
    clean_parts = [part for part in path.parts if part and part != "."]
    if not clean_parts or any(part == ".." for part in clean_parts):
        raise CrdNotesError(
            "Percorso file non valido.",
            detail="Il percorso relativo contiene segmenti non consentiti.",
        )
    if any(":" in part for part in clean_parts):
        raise CrdNotesError(
            "Percorso file non valido.",
            detail="Il percorso relativo contiene caratteri non consentiti.",
        )
    return "/".join(clean_parts)


def _workspace_knowledge_dir(workspace_id: str) -> Path:
    safe_workspace = re.sub(r"[^a-zA-Z0-9_-]", "_", workspace_id).strip("_") or "default"
    path = KNOWLEDGE_DIR / safe_workspace
    path.mkdir(parents=True, exist_ok=True)
    return path


def _knowledge_to_response(file: WorkspaceKnowledgeFile) -> WorkspaceKnowledgeFileResponse:
    return WorkspaceKnowledgeFileResponse(
        id=file.id,
        workspace_id=file.workspace_id,
        original_name=file.original_name,
        content_type=file.content_type,
        extension=file.extension,
        size_bytes=file.size_bytes,
        sha256=file.sha256,
        status=file.status,
        error=file.error,
        created_at=file.created_at,
        updated_at=file.updated_at,
    )


@router.post("/jobs", response_model=JobCreateResponse)
async def create_job(
    runner: Annotated[JobRunner, Depends(get_job_runner)],
    file: Annotated[UploadFile, File()],
    workspace_id: Annotated[str, Form()] = DEFAULT_WORKSPACE_ID,
    title: Annotated[str, Form()] = "",
    recorded_on: Annotated[date | None, Form()] = None,
    notes: Annotated[str, Form()] = "",
    participants: Annotated[str, Form()] = "",
    summarize: Annotated[bool, Form()] = False,
    prompt_id: Annotated[str, Form()] = "riunione_tecnica",
    provider: Annotated[ProviderName | None, Form()] = None,
) -> JobCreateResponse:
    import uuid

    if not _is_allowed_media_upload(file.filename, file.content_type):
        raise CrdNotesError(
            "Formato file non supportato.",
            detail="Carica solo file audio o video.",
        )

    suffix = Path(file.filename or "media").suffix
    source_name = f"{uuid.uuid4()}{suffix}"
    source_path = INBOX_DIR / source_name
    source_path.parent.mkdir(parents=True, exist_ok=True)
    await _write_upload_file_with_limit(
        upload_file=file,
        target_path=source_path,
        max_bytes=_max_media_upload_bytes(),
    )

    payload = {
        "source_path": str(source_path),
        "source_filename": file.filename or source_name,
        "workspace_id": workspace_id or DEFAULT_WORKSPACE_ID,
        "title": title,
        "recorded_on": recorded_on.isoformat() if recorded_on else None,
        "notes": notes,
        "participants": [item.strip() for item in participants.split(",") if item.strip()],
        "summarize": summarize,
        "prompt_id": prompt_id,
        "provider": provider,
    }
    job = runner.create_job(payload)
    return JobCreateResponse(job_id=job.id)


@router.get("/recording/sources", response_model=RecordingSourcesResponse)
def list_recording_sources(
    service: Annotated[RecordingService, Depends(get_recording_service)],
) -> RecordingSourcesResponse:
    return RecordingSourcesResponse(**service.list_sources())


@router.post("/recording/sessions", response_model=RecordingSessionResponse)
def start_recording(
    request: RecordingStartRequest,
    service: Annotated[RecordingService, Depends(get_recording_service)],
) -> RecordingSessionResponse:
    session = service.start(
        workspace_id=request.workspace_id,
        title=request.title,
        recorded_on=request.recorded_on,
        notes=request.notes,
        participants=request.participants,
        mode=request.mode,
        microphone_device=request.microphone_device,
        system_device=request.system_device,
        window_hint=request.window_hint,
    )
    return recording_to_response(session, service=service)


@router.get("/recording/sessions/{session_id}", response_model=RecordingSessionResponse)
def read_recording(
    session_id: str,
    service: Annotated[RecordingService, Depends(get_recording_service)],
) -> RecordingSessionResponse:
    return recording_to_response(service.read(session_id), service=service)


@router.post("/recording/sessions/{session_id}/pause", response_model=RecordingSessionResponse)
def pause_recording(
    session_id: str,
    service: Annotated[RecordingService, Depends(get_recording_service)],
) -> RecordingSessionResponse:
    return recording_to_response(service.pause(session_id), service=service)


@router.post("/recording/sessions/{session_id}/resume", response_model=RecordingSessionResponse)
def resume_recording(
    session_id: str,
    service: Annotated[RecordingService, Depends(get_recording_service)],
) -> RecordingSessionResponse:
    return recording_to_response(service.resume(session_id), service=service)


@router.post("/recording/sessions/{session_id}/bookmarks", response_model=RecordingSessionResponse)
def add_recording_bookmark(
    session_id: str,
    request: RecordingBookmarkCreateRequest,
    service: Annotated[RecordingService, Depends(get_recording_service)],
) -> RecordingSessionResponse:
    return recording_to_response(service.add_bookmark(session_id, request.label), service=service)


@router.post("/recording/sessions/{session_id}/stop", response_model=JobCreateResponse)
def stop_recording(
    session_id: str,
    request: RecordingStopRequest,
    service: Annotated[RecordingService, Depends(get_recording_service)],
) -> JobCreateResponse:
    job_id = service.stop(
        session_id,
        summarize=request.summarize,
        prompt_id=request.prompt_id,
        provider=request.provider,
    )
    return JobCreateResponse(job_id=job_id)


@router.delete("/recording/sessions/{session_id}", status_code=204)
def cancel_recording(
    session_id: str,
    service: Annotated[RecordingService, Depends(get_recording_service)],
) -> Response:
    service.cancel(session_id)
    return Response(status_code=204)


async def _write_upload_file_with_limit(
    *,
    upload_file: UploadFile,
    target_path: Path,
    max_bytes: int,
) -> None:
    size_bytes = 0
    with target_path.open("wb") as target:
        while chunk := await upload_file.read(1024 * 1024):
            size_bytes += len(chunk)
            if size_bytes > max_bytes:
                target.close()
                target_path.unlink(missing_ok=True)
                limit_mb = max_bytes // (1024 * 1024)
                raise CrdNotesError(
                    "File troppo grande.",
                    detail=f"Dimensione massima consentita: {limit_mb} MB per file audio/video.",
                )
            target.write(chunk)


@router.get("/jobs", response_model=list[JobStatusResponse])
def list_jobs(
    repository: Annotated[LibraryRepository, Depends(get_repository)],
    active: bool = False,
) -> list[JobStatusResponse]:
    if active:
        return [job_to_response(job) for job in repository.list_open_jobs()]
    return []


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def read_job(
    job_id: str,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
) -> JobStatusResponse:
    job = repository.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job non trovato.")
    return job_to_response(job)


@router.get("/library", response_model=list[LibraryEntryListResponse])
def list_library(
    repository: Annotated[LibraryRepository, Depends(get_repository)],
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    q: str = "",
    participant: str = "",
    keyword: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    summary_filter: str = "all",
) -> list[LibraryEntryListResponse]:
    counts = repository.library_counts()
    metadata = repository.entry_metadata()
    return [
        entry_to_response(
            entry,
            counts=counts.get(entry.id, {}),
            metadata=metadata.get(entry.id, {}),
        )
        for entry in repository.list_entries(
            workspace_id or DEFAULT_WORKSPACE_ID,
            query=q,
            participant=participant,
            keyword=keyword,
            date_from=date_from,
            date_to=date_to,
            summary_filter=summary_filter,
            include_transcript=False,
        )
    ]


@router.get("/library/{entry_id}", response_model=LibraryDetailResponse)
def read_entry(
    entry_id: str,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
) -> LibraryDetailResponse:
    entry = repository.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Trascrizione non trovata.")
    summaries = repository.list_summaries(entry_id)
    counts = repository.library_counts().get(entry_id, {})
    metadata = repository.list_summary_metadata(entry_id)
    entry_metadata = repository.entry_metadata().get(entry_id, {})
    return LibraryDetailResponse(
        entry=entry_detail_to_response(entry, counts=counts, metadata=entry_metadata),
        summaries=[summary_to_response(item, metadata=metadata.get(item.id)) for item in summaries],
    )


def _slugify_filename(value: str, fallback: str) -> str:
    slug = "".join(
        char.lower() if char.isalnum() else "-"
        for char in value.strip()
    ).strip("-")
    return slug or fallback


@router.get("/library/{entry_id}/transcript.md")
def download_transcript(
    entry_id: str,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
) -> Response:
    entry = repository.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Trascrizione non trovata.")

    filename = f"{_slugify_filename(entry.title, 'titolo')}_trascrizione.md"
    return Response(
        content=entry.transcript,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/library/{entry_id}/summary.md")
def download_summary(
    entry_id: str,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
) -> Response:
    entry = repository.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Trascrizione non trovata.")

    summaries = repository.list_summaries(entry_id)
    if not summaries:
        raise HTTPException(status_code=404, detail="Riassunto non trovato.")

    latest_summary = summaries[0]
    filename = f"{_slugify_filename(entry.title, 'titolo')}_riassunto.md"
    return Response(
        content=latest_summary.content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/library/{entry_id}/summaries", response_model=SummaryResponse)
async def create_summary(
    entry_id: str,
    request: SummaryCreateRequest,
    summary_workflow: Annotated[SummaryWorkflowService, Depends(get_summary_workflow_service)],
    settings_store: Annotated[SettingsStore, Depends(get_settings_store)],
) -> SummaryResponse:
    settings = settings_store.load()
    result = await summary_workflow.generate_for_entry(
        entry_id=entry_id,
        prompt_id=request.prompt_id,
        settings=settings,
        provider=request.provider if request.provider else None,
        model=request.model,
    )
    return summary_to_response(result.summary, metadata=result.metadata)


@router.get("/operations", response_model=list[OperationItemResponse])
def list_operations(
    repository: Annotated[LibraryRepository, Depends(get_repository)],
    workspace_id: str = DEFAULT_WORKSPACE_ID,
) -> list[OperationItemResponse]:
    workspace_id = workspace_id or DEFAULT_WORKSPACE_ID
    entries = {entry.id: entry for entry in repository.list_entries(workspace_id)}
    return [
        operation_to_response(item, entry=entries.get(item.entry_id))
        for item in repository.list_operation_items(workspace_id=workspace_id)
    ]


@router.patch("/operations/{item_id}", response_model=OperationItemResponse)
def update_operation(
    item_id: str,
    request: OperationItemUpdateRequest,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
    operation_service: Annotated[OperationService, Depends(get_operation_service)],
    settings_store: SettingsStore = Depends(get_settings_store),
    rag_service: RagService = Depends(get_rag_service),
) -> OperationItemResponse:
    current = repository.get_operation_item(item_id)
    if not current:
        raise LibraryError("Elemento operativo non trovato.")
    due_date = request.due_date if "due_date" in request.model_fields_set else current.due_date
    item = operation_service.update_item(
        item_id,
        text=request.text if "text" in request.model_fields_set else None,
        owner=request.owner if "owner" in request.model_fields_set else None,
        due_date=due_date,
        status=request.status if "status" in request.model_fields_set else None,
    )
    reindex_entry_if_enabled(
        settings_store=settings_store,
        rag_service=rag_service,
        entry_id=item.entry_id,
    )
    return operation_to_response(item, entry=repository.get_entry(item.entry_id))


@router.delete("/operations/{item_id}")
def delete_operation(
    item_id: str,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
    settings_store: SettingsStore = Depends(get_settings_store),
    rag_service: RagService = Depends(get_rag_service),
) -> dict[str, str]:
    current = repository.get_operation_item(item_id)
    if current is None:
        raise LibraryError("Elemento operativo non trovato.")
    repository.delete_operation_item(item_id)
    reindex_entry_if_enabled(
        settings_store=settings_store,
        rag_service=rag_service,
        entry_id=current.entry_id,
    )
    return {"status": "deleted"}


@router.post("/library/{entry_id}/operations/extract", response_model=OperationExtractResponse)
def extract_operations(
    entry_id: str,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
    operation_service: Annotated[OperationService, Depends(get_operation_service)],
    settings_store: SettingsStore = Depends(get_settings_store),
    rag_service: RagService = Depends(get_rag_service),
) -> OperationExtractResponse:
    entry = repository.get_entry(entry_id)
    items = operation_service.extract_from_latest_summary(entry_id)
    reindex_entry_if_enabled(
        settings_store=settings_store,
        rag_service=rag_service,
        entry_id=entry_id,
    )
    return OperationExtractResponse(
        items=[operation_to_response(item, entry=entry) for item in items]
    )


@router.post("/library/{entry_id}/operations/ai-extract", response_model=OperationExtractResponse)
async def ai_extract_operations(
    entry_id: str,
    repository: Annotated[LibraryRepository, Depends(get_repository)],
    operation_service: Annotated[OperationService, Depends(get_operation_service)],
    settings_store: SettingsStore = Depends(get_settings_store),
    ai_service: AiService = Depends(get_ai_service),
    rag_service: RagService = Depends(get_rag_service),
) -> OperationExtractResponse:
    entry = repository.get_entry(entry_id)
    if not entry:
        raise LibraryError("Trascrizione non trovata.")
    summaries = repository.list_summaries(entry_id)
    if not summaries:
        raise LibraryError("Nessun riassunto disponibile per questa trascrizione.")
    latest_summary = summaries[0]
    settings = settings_store.load()
    result = await ai_service.complete_with_prompt(
        input_text=f"Titolo: {entry.title}\n\nSummary:\n{latest_summary.content}",
        system_prompt=AI_EXTRACTION_PROMPT,
        settings=settings,
    )
    items = operation_service.replace_ai_extraction(entry_id, result.content)
    reindex_entry_if_enabled(
        settings_store=settings_store,
        rag_service=rag_service,
        entry_id=entry_id,
    )
    return OperationExtractResponse(
        items=[operation_to_response(item, entry=entry) for item in items]
    )


def _append_rag_context(base_input: str, rag_context: str) -> str:
    if not rag_context.strip():
        return base_input
    return f"{base_input}\n\nContesto RAG workspace:\n{rag_context}"


def entry_to_response(
    entry: LibraryEntry,
    *,
    counts: dict[str, int] | None = None,
    metadata: dict[str, list[str] | str] | None = None,
) -> LibraryEntryListResponse:
    counts = counts or {}
    metadata = metadata or {}
    return LibraryEntryListResponse(
        id=entry.id,
        workspace_id=entry.workspace_id,
        title=entry.title,
        notes=entry.notes,
        participants=entry.participants,
        source_filename=entry.source_filename,
        audio_filename=entry.audio_filename,
        duration_seconds=entry.duration_seconds,
        recorded_on=entry.recorded_on,
        created_at=entry.created_at,
        summary_count=counts.get("summary_count", 0),
        operation_open_count=counts.get("operation_open_count", 0),
        operation_total_count=counts.get("operation_total_count", 0),
        tags=metadata.get("tags", []),
        keywords=metadata.get("keywords", []),
        people=metadata.get("people", []),
        topics=metadata.get("topics", []),
    )


def entry_detail_to_response(
    entry: LibraryEntry,
    *,
    counts: dict[str, int] | None = None,
    metadata: dict[str, list[str] | str] | None = None,
) -> LibraryEntryDetailResponse:
    base = entry_to_response(entry, counts=counts, metadata=metadata)
    return LibraryEntryDetailResponse(**base.model_dump(), transcript=entry.transcript)


def summary_to_response(summary: Summary, *, metadata=None) -> SummaryResponse:
    if metadata is None:
        return SummaryResponse(**summary.__dict__)
    return SummaryResponse(
        **summary.__dict__,
        tags=metadata.tags,
        keywords=metadata.keywords,
        people=metadata.people,
        topics=metadata.topics,
        context=metadata.context,
    )


def chat_thread_to_response(thread: ChatThread) -> ChatThreadResponse:
    return ChatThreadResponse(**thread.__dict__)


def chat_message_to_response(
    message: ChatMessage,
    *,
    sources: list[ChatMessageSource] | None = None,
) -> ChatMessageResponse:
    followups = []
    if message.role == "assistant":
        from crd_notes.chat.context import extract_followups

        followups = extract_followups(message.content)
    return ChatMessageResponse(
        **message.__dict__,
        sources=[chat_source_to_response(source) for source in sources or []],
        followups=followups,
    )


def chat_source_to_response(source: ChatMessageSource) -> ChatMessageSourceResponse:
    return ChatMessageSourceResponse(**source.__dict__)


def workspace_to_response(workspace: Workspace) -> WorkspaceResponse:
    return WorkspaceResponse(**workspace.__dict__)


def workspace_intelligence_to_response(
    intelligence: WorkspaceIntelligence,
) -> WorkspaceIntelligenceResponse:
    return WorkspaceIntelligenceResponse(
        workspace_id=intelligence.workspace_id,
        generated_at=intelligence.generated_at,
        entry_count=intelligence.entry_count,
        summary_count=intelligence.summary_count,
        operation_open_count=intelligence.operation_open_count,
        top_tags=[IntelligenceItemResponse(**item.__dict__) for item in intelligence.top_tags],
        top_keywords=[
            IntelligenceItemResponse(**item.__dict__) for item in intelligence.top_keywords
        ],
        top_people=[IntelligenceItemResponse(**item.__dict__) for item in intelligence.top_people],
        top_topics=[IntelligenceItemResponse(**item.__dict__) for item in intelligence.top_topics],
        clusters=[
            IntelligenceClusterResponse(**cluster.__dict__)
            for cluster in intelligence.clusters
        ],
        decisions=[
            IntelligenceTimelineItemResponse(**item.__dict__)
            for item in intelligence.decisions
        ],
        risks=[
            IntelligenceTimelineItemResponse(**item.__dict__)
            for item in intelligence.risks
        ],
        questions=[
            IntelligenceTimelineItemResponse(**item.__dict__)
            for item in intelligence.questions
        ],
        local_brief=intelligence.local_brief,
    )


def operation_to_response(
    item: OperationItem,
    *,
    entry: LibraryEntry | None = None,
) -> OperationItemResponse:
    entry_meta = None
    if entry is not None:
        entry_meta = OperationEntryMeta(
            id=entry.id,
            workspace_id=entry.workspace_id,
            title=entry.title,
            recorded_on=entry.recorded_on,
            created_at=entry.created_at,
        )
    return OperationItemResponse(**item.__dict__, entry=entry_meta)


def job_to_response(job: Job) -> JobStatusResponse:
    return JobStatusResponse(
        id=job.id,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        message=job.message,
        error=job.error,
        entry_id=job.entry_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def recording_to_response(session, *, service: RecordingService) -> RecordingSessionResponse:
    return RecordingSessionResponse(
        id=session.id,
        workspace_id=session.workspace_id,
        title=session.title,
        recorded_on=session.recorded_on,
        notes=session.notes,
        participants=session.participants,
        mode=session.mode,
        microphone_device=session.microphone_device,
        system_device=session.system_device,
        window_hint=session.window_hint,
        status=session.status,
        elapsed_seconds=service.elapsed_seconds(session),
        bookmarks=[
            RecordingBookmarkResponse(
                id=bookmark.id,
                label=bookmark.label,
                timestamp_seconds=bookmark.timestamp_seconds,
                created_at=bookmark.created_at,
            )
            for bookmark in session.bookmarks
        ],
        created_at=session.created_at,
        updated_at=session.updated_at,
        error=session.error,
    )
