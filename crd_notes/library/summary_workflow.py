from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from crd_notes.ai.service import AiService
from crd_notes.core.config import AppSettings, ProviderName
from crd_notes.core.errors import CrdNotesError, LibraryError
from crd_notes.library.models import LibraryEntry, Summary, SummaryMetadata
from crd_notes.library.operations import OperationService
from crd_notes.library.repository import LibraryRepository
from crd_notes.library.service import LibraryService
from crd_notes.library.summary_metadata import (
    SUMMARY_METADATA_PROMPT,
    SummaryMetadataService,
    build_summary_metadata_input,
)
from crd_notes.rag import SUMMARY_ENRICHMENT_PROMPT, RagService, build_summary_enrichment_input

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SummaryWorkflowResult:
    summary: Summary
    metadata: SummaryMetadata | None = None


class SummaryWorkflowService:
    def __init__(
        self,
        *,
        repository: LibraryRepository,
        library_service: LibraryService,
        operation_service: OperationService,
        summary_metadata_service: SummaryMetadataService,
        ai_service: AiService,
        rag_service: RagService,
    ) -> None:
        self.repository = repository
        self.library_service = library_service
        self.operation_service = operation_service
        self.summary_metadata_service = summary_metadata_service
        self.ai_service = ai_service
        self.rag_service = rag_service

    async def generate_for_entry(
        self,
        *,
        entry_id: str,
        prompt_id: str,
        settings: AppSettings,
        provider: ProviderName | None = None,
        model: str | None = None,
    ) -> SummaryWorkflowResult:
        entry = self.repository.get_entry(entry_id)
        if not entry:
            raise LibraryError("Trascrizione non trovata.")

        result = await self.ai_service.summarize(
            transcript=entry.transcript,
            prompt_id=prompt_id,
            settings=settings,
            provider=provider,
            model=model,
        )
        summary_content = result.content
        summary_provider = result.provider
        summary_model = result.model

        enriched = await self._enrich_summary(
            entry=entry,
            base_summary=result.content,
            settings=settings,
            provider=provider,
            model=model,
        )
        if enriched is not None:
            summary_content = enriched.content
            summary_provider = enriched.provider
            summary_model = enriched.model

        summary = self.library_service.add_summary(
            entry_id=entry.id,
            provider=summary_provider,
            model=summary_model,
            prompt_id=prompt_id,
            content=summary_content,
        )
        self._extract_operations(entry.id)
        metadata = await self._extract_metadata(
            entry_title=entry.title,
            prompt_id=prompt_id,
            summary=summary,
            settings=settings,
            provider=provider,
            model=model,
        )
        self.index_entry(entry.id, settings)
        return SummaryWorkflowResult(summary=summary, metadata=metadata)

    async def generate_for_entry_stream(
        self,
        *,
        entry_id: str,
        prompt_id: str,
        settings: AppSettings,
        provider: ProviderName | None = None,
        model: str | None = None,
    ) -> AsyncIterator[dict[str, object]]:
        entry = self.repository.get_entry(entry_id)
        if not entry:
            raise LibraryError("Trascrizione non trovata.")

        selected_provider = provider or settings.active_provider
        provider_settings = settings.providers[selected_provider]
        summary_provider = selected_provider
        summary_model = model or provider_settings.model
        chunks: list[str] = []

        yield {"type": "status", "message": "Generazione riassunto in corso."}
        async for chunk in self.ai_service.stream_summary(
            transcript=entry.transcript,
            prompt_id=prompt_id,
            settings=settings,
            provider=provider,
            model=model,
        ):
            chunks.append(chunk)
            yield {"type": "delta", "content": chunk}

        summary_content = "".join(chunks).strip()
        if not summary_content:
            raise LibraryError("Ollama non ha restituito testo.")

        enriched = await self._enrich_summary(
            entry=entry,
            base_summary=summary_content,
            settings=settings,
            provider=provider,
            model=model,
        )
        if enriched is not None:
            summary_content = enriched.content
            summary_provider = enriched.provider
            summary_model = enriched.model
            yield {"type": "replace", "content": summary_content}

        yield {"type": "status", "message": "Salvataggio riassunto e metadati."}
        summary = self.library_service.add_summary(
            entry_id=entry.id,
            provider=summary_provider,
            model=summary_model,
            prompt_id=prompt_id,
            content=summary_content,
        )
        self._extract_operations(entry.id)
        metadata = await self._extract_metadata(
            entry_title=entry.title,
            prompt_id=prompt_id,
            summary=summary,
            settings=settings,
            provider=provider,
            model=model,
        )
        self.index_entry(entry.id, settings)
        yield {"type": "done", "summary": summary, "metadata": metadata}

    def index_entry(self, entry_id: str, settings: AppSettings) -> None:
        self._safe_index_entry(entry_id, settings)

    async def _enrich_summary(
        self,
        *,
        entry: LibraryEntry,
        base_summary: str,
        settings: AppSettings,
        provider: ProviderName | None,
        model: str | None,
    ):
        if not settings.rag.enabled or not settings.rag.enrich_summaries:
            return None
        try:
            rag_context = self.rag_service.build_context(
                workspace_id=entry.workspace_id,
                query_text=_summary_query(title=entry.title, notes=entry.notes, summary=base_summary),
                settings=settings,
                doc_types=_summary_doc_types(settings),
            )
            if not rag_context.context_text:
                return None
            return await self.ai_service.complete_with_prompt(
                input_text=build_summary_enrichment_input(
                    title=entry.title,
                    notes=entry.notes,
                    participants=entry.participants,
                    base_summary=base_summary,
                    rag_context=rag_context.context_text,
                ),
                system_prompt=SUMMARY_ENRICHMENT_PROMPT,
                settings=settings,
                provider=provider,
                model=model,
            )
        except CrdNotesError as exc:
            logger.warning("Arricchimento RAG non disponibile per %s: %s", entry.id, exc.message)
            return None
        except Exception as exc:  # pragma: no cover - fallback difensivo
            logger.warning("Errore arricchimento RAG per %s: %s", entry.id, exc)
            return None

    def _extract_operations(self, entry_id: str) -> None:
        try:
            self.operation_service.extract_from_latest_summary(entry_id)
        except CrdNotesError as exc:
            logger.warning("Elementi operativi non estratti per %s: %s", entry_id, exc.message)
        except Exception as exc:  # pragma: no cover - fallback difensivo
            logger.warning("Errore estrazione elementi operativi per %s: %s", entry_id, exc)

    async def _extract_metadata(
        self,
        *,
        entry_title: str,
        prompt_id: str,
        summary: Summary,
        settings: AppSettings,
        provider: ProviderName | None,
        model: str | None,
    ) -> SummaryMetadata | None:
        try:
            result = await self.ai_service.complete_with_prompt(
                input_text=build_summary_metadata_input(
                    prompt_id=prompt_id,
                    title=entry_title,
                    summary=summary.content,
                ),
                system_prompt=SUMMARY_METADATA_PROMPT,
                settings=settings,
                provider=provider,
                model=model,
            )
            return self.summary_metadata_service.save_from_ai(
                summary=summary,
                raw_json=result.content,
            )
        except CrdNotesError as exc:
            logger.warning("Metadati summary non generati per %s: %s", summary.id, exc.message)
            return None
        except Exception as exc:  # pragma: no cover - fallback difensivo
            logger.warning("Errore metadati summary per %s: %s", summary.id, exc)
            return None

    def _safe_index_entry(self, entry_id: str, settings: AppSettings) -> None:
        if not settings.rag.enabled:
            return
        try:
            self.rag_service.index_entry(entry_id, settings)
        except CrdNotesError as exc:
            logger.warning("Indicizzazione RAG non disponibile per %s: %s", entry_id, exc.message)
        except Exception as exc:  # pragma: no cover - fallback difensivo
            logger.warning("Errore indicizzazione RAG per %s: %s", entry_id, exc)


def _summary_doc_types(settings: AppSettings) -> list[str]:
    doc_types: list[str] = ["note"]
    if settings.rag.enrich_with_transcript_chunks:
        doc_types.append("transcript")
    if settings.rag.enrich_with_summary_chunks:
        doc_types.append("summary")
    if settings.rag.enrich_with_metadata_chunks:
        doc_types.append("metadata")
    if settings.rag.enrich_with_operation_chunks:
        doc_types.append("operation")
    if settings.rag.enrich_with_knowledge_chunks:
        doc_types.append("knowledge_file")
    return doc_types


def _summary_query(*, title: str, notes: str, summary: str) -> str:
    return "\n".join(
        [
            f"Titolo: {title}",
            f"Note: {notes}" if notes else "",
            "Obiettivo: recupera contesto storico utile per completare il riassunto.",
            summary,
        ]
    )
