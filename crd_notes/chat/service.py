from __future__ import annotations

import uuid
from dataclasses import dataclass

from crd_notes.ai.service import AiService
from crd_notes.chat.context import (
    build_retrieval_query,
    clean_assistant_content,
    compact_chunks,
    compact_history,
)
from crd_notes.chat.prompts import (
    CHAT_QUERY_REWRITE_PROMPT,
    build_chat_input,
    build_query_rewrite_input,
    get_chat_system_prompt,
)
from crd_notes.core.config import AppSettings, ProviderName
from crd_notes.core.errors import LibraryError
from crd_notes.library.models import ChatMessage, ChatMessageSource, ChatThread, LibraryEntry
from crd_notes.library.repository import LibraryRepository, utc_now
from crd_notes.rag import RagContext, RagService


CHAT_SOURCE_LIMIT = 8
CHAT_DOC_TYPES = ["transcript", "summary", "metadata", "operation", "note", "knowledge_file"]


@dataclass(frozen=True)
class ChatTurn:
    thread: ChatThread
    user_message: ChatMessage
    assistant_message: ChatMessage
    sources: list[ChatMessageSource]


class WorkspaceChatService:
    def __init__(
        self,
        *,
        repository: LibraryRepository,
        rag_service: RagService,
        ai_service: AiService,
    ) -> None:
        self.repository = repository
        self.rag_service = rag_service
        self.ai_service = ai_service

    def create_thread(self, *, workspace_id: str, title: str = "") -> ChatThread:
        workspace = self.repository.get_workspace(workspace_id)
        if workspace is None:
            raise LibraryError("Workspace non trovato.")
        now = utc_now()
        thread = ChatThread(
            id=uuid.uuid4().hex,
            workspace_id=workspace_id,
            title=_thread_title(title),
            created_at=now,
            updated_at=now,
        )
        self.repository.add_chat_thread(thread)
        return thread

    def rename_thread(self, *, thread_id: str, workspace_id: str, title: str) -> ChatThread:
        thread = self._thread_in_workspace(thread_id=thread_id, workspace_id=workspace_id)
        updated = self.repository.update_chat_thread(
            thread.id,
            title=_thread_title(title),
            updated_at=utc_now(),
        )
        if updated is None:
            raise LibraryError("Chat non trovata.")
        return updated

    def delete_thread(self, *, thread_id: str, workspace_id: str) -> None:
        thread = self._thread_in_workspace(thread_id=thread_id, workspace_id=workspace_id)
        self.repository.delete_chat_thread(thread.id)

    async def send_message(
        self,
        *,
        thread_id: str | None,
        workspace_id: str,
        content: str,
        mentioned_entry_ids: list[str],
        mentioned_knowledge_folders: list[str],
        settings: AppSettings,
        provider: ProviderName | None = None,
        model: str | None = None,
    ) -> ChatTurn:
        clean_content = content.strip()
        if not clean_content:
            raise LibraryError("Scrivi un messaggio prima di inviare.")
        thread = (
            self._thread_in_workspace(thread_id=thread_id, workspace_id=workspace_id)
            if thread_id
            else self.create_thread(workspace_id=workspace_id, title=_title_from_message(clean_content))
        )
        mentioned_entries = self._mentioned_entries(
            workspace_id=workspace_id,
            mentioned_entry_ids=mentioned_entry_ids,
        )
        history = self.repository.list_chat_messages(thread.id)
        clean_folders = _clean_folders(mentioned_knowledge_folders)
        compacted_history = compact_history(history)
        fallback_query = build_retrieval_query(
            user_message=clean_content,
            history=history,
            mentioned_titles=[entry.title for entry in mentioned_entries],
            mentioned_folders=clean_folders,
        )
        retrieval_query = await self._rewrite_query(
            user_message=clean_content,
            compacted_history=compacted_history,
            fallback_query=fallback_query,
            mentioned_titles=[entry.title for entry in mentioned_entries],
            mentioned_folders=clean_folders,
            settings=settings,
            provider=provider,
            model=model,
        )
        rag_context = self._build_rag_context(
            workspace_id=workspace_id,
            query_text=retrieval_query,
            mentioned_entries=mentioned_entries,
            mentioned_knowledge_folders=clean_folders,
            settings=settings,
        )
        compacted_context = compact_chunks(
            rag_context.chunks,
            max_chars=settings.rag.max_context_chars,
        )
        input_text = build_chat_input(
            user_message=clean_content,
            rag_context=compacted_context.text,
            rag_evidence=compacted_context.evidence,
            history=compacted_history,
            mentioned_titles=[entry.title for entry in mentioned_entries],
            mentioned_folders=clean_folders,
        )
        result = await self.ai_service.complete_with_prompt(
            input_text=input_text,
            system_prompt=get_chat_system_prompt(),
            settings=settings,
            provider=provider,
            model=model,
        )
        assistant_content = clean_assistant_content(result.content)

        now = utc_now()
        user_message = ChatMessage(
            id=uuid.uuid4().hex,
            thread_id=thread.id,
            role="user",
            content=clean_content,
            provider="",
            model="",
            created_at=now,
        )
        assistant_message = ChatMessage(
            id=uuid.uuid4().hex,
            thread_id=thread.id,
            role="assistant",
            content=assistant_content,
            provider=result.provider,
            model=result.model,
            created_at=utc_now(),
        )
        self.repository.add_chat_message(user_message)
        self.repository.add_chat_message(assistant_message)

        sources = _sources_from_chunks(assistant_message.id, compacted_context.chunks)
        self.repository.add_chat_message_sources(sources)
        title = thread.title
        if title == "Nuova chat":
            title = _title_from_message(clean_content)
        updated_thread = self.repository.update_chat_thread(
            thread.id,
            title=title,
            updated_at=assistant_message.created_at,
        )
        return ChatTurn(
            thread=updated_thread or thread,
            user_message=user_message,
            assistant_message=assistant_message,
            sources=sources,
        )

    async def _rewrite_query(
        self,
        *,
        user_message: str,
        compacted_history: str,
        fallback_query: str,
        mentioned_titles: list[str],
        mentioned_folders: list[str],
        settings: AppSettings,
        provider: ProviderName | None,
        model: str | None,
    ) -> str:
        if not compacted_history.strip():
            return fallback_query
        try:
            result = await self.ai_service.complete_with_prompt(
                input_text=build_query_rewrite_input(
                    user_message=user_message,
                    history=compacted_history,
                    mentioned_titles=mentioned_titles,
                    mentioned_folders=mentioned_folders,
                ),
                system_prompt=CHAT_QUERY_REWRITE_PROMPT,
                settings=settings,
                provider=provider,
                model=model,
            )
        except Exception:
            return fallback_query
        rewritten = result.content.strip().strip('"').strip()
        if not rewritten or len(rewritten) > 700:
            return fallback_query
        return rewritten

    def _thread_in_workspace(self, *, thread_id: str | None, workspace_id: str) -> ChatThread:
        if not thread_id:
            raise LibraryError("Chat non trovata.")
        thread = self.repository.get_chat_thread(thread_id)
        if thread is None or thread.workspace_id != workspace_id:
            raise LibraryError("Chat non trovata in questo workspace.")
        return thread

    def _mentioned_entries(
        self,
        *,
        workspace_id: str,
        mentioned_entry_ids: list[str],
    ) -> list[LibraryEntry]:
        entries: list[LibraryEntry] = []
        seen: set[str] = set()
        for entry_id in mentioned_entry_ids:
            if entry_id in seen:
                continue
            seen.add(entry_id)
            entry = self.repository.get_entry(entry_id)
            if entry is None or entry.workspace_id != workspace_id:
                raise LibraryError("Una riunione taggata non appartiene al workspace attivo.")
            entries.append(entry)
        return entries

    def _build_rag_context(
        self,
        *,
        workspace_id: str,
        query_text: str,
        mentioned_entries: list[LibraryEntry],
        mentioned_knowledge_folders: list[str],
        settings: AppSettings,
    ) -> RagContext:
        entry_ids = [entry.id for entry in mentioned_entries]
        clean_folders = _clean_folders(mentioned_knowledge_folders)
        focused_chunks = []

        if entry_ids:
            meeting_context = self.rag_service.build_context(
                workspace_id=workspace_id,
                query_text=query_text,
                settings=settings,
                doc_types=["transcript", "summary", "metadata", "operation", "note"],
                entry_ids=entry_ids,
                top_k=CHAT_SOURCE_LIMIT,
                candidate_k=settings.rag.candidate_k,
            )
            focused_chunks.extend(meeting_context.chunks)

        if clean_folders:
            knowledge_context = self.rag_service.build_context(
                workspace_id=workspace_id,
                query_text=query_text,
                settings=settings,
                doc_types=["knowledge_file"],
                knowledge_folders=clean_folders,
                top_k=CHAT_SOURCE_LIMIT,
                candidate_k=settings.rag.candidate_k,
            )
            focused_chunks.extend(knowledge_context.chunks)

        if not entry_ids and not clean_folders:
            return self.rag_service.build_context(
                workspace_id=workspace_id,
                query_text=query_text,
                settings=settings,
                doc_types=CHAT_DOC_TYPES,
                top_k=settings.rag.top_k,
                candidate_k=settings.rag.candidate_k,
            )

        if clean_folders:
            return RagContext(
                chunks=focused_chunks[:CHAT_SOURCE_LIMIT],
                context_text="",
            )

        workspace_context = self.rag_service.build_context(
            workspace_id=workspace_id,
            query_text=query_text,
            settings=settings,
            doc_types=CHAT_DOC_TYPES,
            top_k=max(3, min(5, settings.rag.top_k)),
            candidate_k=max(settings.rag.candidate_k // 2, settings.rag.top_k),
        )
        chunks = _merge_chunks(RagContext(chunks=focused_chunks, context_text=""), workspace_context)
        return RagContext(chunks=chunks, context_text="")


def _thread_title(value: str) -> str:
    return value.strip()[:80] or "Nuova chat"


def _title_from_message(value: str) -> str:
    first_line = value.strip().splitlines()[0] if value.strip() else ""
    return _thread_title(first_line)


def _merge_chunks(primary: RagContext, secondary: RagContext):
    chunks = []
    seen: set[tuple[str, str, str]] = set()
    for chunk in [*primary.chunks, *secondary.chunks]:
        key = (chunk.entry_id, chunk.doc_type, chunk.text)
        if key in seen:
            continue
        seen.add(key)
        chunks.append(chunk)
    return chunks[:CHAT_SOURCE_LIMIT]


def _clean_folders(folders: list[str]) -> list[str]:
    cleaned: list[str] = []
    for folder in folders:
        normalized = folder.replace("\\", "/").strip().strip("/")
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def _sources_from_chunks(message_id: str, chunks) -> list[ChatMessageSource]:
    now = utc_now()
    sources: list[ChatMessageSource] = []
    for chunk in chunks[:CHAT_SOURCE_LIMIT]:
        sources.append(
            ChatMessageSource(
                id=uuid.uuid4().hex,
                message_id=message_id,
                entry_id=chunk.entry_id,
                entry_title=chunk.entry_title,
                doc_type=chunk.doc_type,
                source=chunk.source,
                score=chunk.score,
                snippet=chunk.text,
                created_at=now,
            )
        )
    return sources
