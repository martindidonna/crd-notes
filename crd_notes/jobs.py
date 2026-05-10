from __future__ import annotations

import asyncio
import logging
import queue
import threading
from datetime import date
from pathlib import Path

from crd_notes.conversion import MediaConverter
from crd_notes.core.config import SettingsStore
from crd_notes.core.errors import CrdNotesError
from crd_notes.core.paths import AUDIO_DIR
from crd_notes.library.models import Job
from crd_notes.library.repository import LibraryRepository, utc_now
from crd_notes.library.service import LibraryService
from crd_notes.library.summary_workflow import SummaryWorkflowService
from crd_notes.transcription import WhisperTranscriber

logger = logging.getLogger(__name__)


class JobRunner:
    def __init__(
        self,
        *,
        repository: LibraryRepository,
        library_service: LibraryService,
        settings_store: SettingsStore,
        converter: MediaConverter,
        transcriber: WhisperTranscriber,
        summary_workflow_service: SummaryWorkflowService,
    ) -> None:
        self.repository = repository
        self.library_service = library_service
        self.settings_store = settings_store
        self.converter = converter
        self.transcriber = transcriber
        self.summary_workflow_service = summary_workflow_service
        self._queue: queue.Queue[str] = queue.Queue()
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        thread = threading.Thread(target=self._work_loop, name="crd-notes-jobs", daemon=True)
        thread.start()
        for job in self.repository.list_open_jobs():
            self.enqueue(job.id)

    def create_job(self, payload: dict) -> Job:
        import uuid

        now = utc_now()
        job = Job(
            id=str(uuid.uuid4()),
            status="queued",
            stage="upload",
            progress=5,
            message="File acquisito. In attesa di elaborazione.",
            error=None,
            entry_id=None,
            payload=payload,
            created_at=now,
            updated_at=now,
        )
        self.repository.create_job(job)
        self.enqueue(job.id)
        return job

    def enqueue(self, job_id: str) -> None:
        self._queue.put(job_id)

    def _work_loop(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                self._process(job_id)
            finally:
                self._queue.task_done()

    def _process(self, job_id: str) -> None:
        job = self.repository.get_job(job_id)
        if not job:
            return

        logger.info("Avvio job %s", job_id)
        payload = job.payload
        source = Path(payload["source_path"])
        audio_path = AUDIO_DIR / f"{job_id}.wav"
        settings = self.settings_store.load()

        try:
            self.repository.update_job(
                job_id,
                status="running",
                stage="conversion",
                progress=20,
                message="Conversione audio in corso.",
            )
            converted_path, duration = self.converter.to_wav(source, audio_path)

            self.repository.update_job(
                job_id,
                stage="transcription",
                progress=28,
                message="Trascrizione Whisper in avvio.",
            )

            def report_transcription_progress(percent: int, message: str) -> None:
                progress = 28 + int(percent * 0.58)
                self.repository.update_job(
                    job_id,
                    stage="transcription",
                    progress=min(86, progress),
                    message=message,
                )

            transcript = self.transcriber.transcribe(
                converted_path,
                model_name=settings.whisper_model,
                language=settings.transcription_language,
                device=settings.whisper_device,
                compute_type=settings.whisper_compute_type,
                beam_size=settings.whisper_beam_size,
                cpu_threads=settings.whisper_cpu_threads,
                workers=settings.whisper_workers,
                vad_filter=settings.whisper_vad_filter,
                condition_on_previous_text=settings.whisper_condition_on_previous_text,
                duration_seconds=duration,
                on_progress=report_transcription_progress,
            )

            self.repository.update_job(
                job_id,
                stage="library",
                progress=90,
                message="Salvataggio in libreria.",
            )
            entry = self.library_service.create_entry(
                workspace_id=payload.get("workspace_id") or "default",
                title=payload.get("title") or source.name,
                notes=payload.get("notes") or "",
                participants=payload.get("participants") or [],
                source_filename=payload.get("source_filename") or source.name,
                audio_filename=converted_path.name,
                duration_seconds=duration,
                recorded_on=_parse_recorded_on(payload.get("recorded_on")),
                transcript=transcript,
            )

            if payload.get("summarize"):
                self.repository.update_job(
                    job_id,
                    stage="summary",
                    progress=86,
                    message="Riassunto AI in corso.",
                    entry_id=entry.id,
                )
                prompt_id = payload.get("prompt_id") or settings.active_prompt
                provider = payload.get("provider")
                asyncio.run(
                    self.summary_workflow_service.generate_for_entry(
                        entry_id=entry.id,
                        prompt_id=prompt_id,
                        settings=settings,
                        provider=provider,
                    )
                )
            elif settings.rag.enabled:
                self.summary_workflow_service.index_entry(entry.id, settings)

            self.repository.update_job(
                job_id,
                status="completed",
                stage="completed",
                progress=100,
                message="Elaborazione completata.",
                entry_id=entry.id,
            )
            logger.info("Job %s completato", job_id)
        except CrdNotesError as exc:
            self.repository.update_job(
                job_id,
                status="failed",
                stage="failed",
                progress=100,
                message=exc.message,
                error=exc.detail or exc.message,
            )
            logger.warning("Job %s fallito: %s", job_id, exc.message)
        except Exception as exc:  # pragma: no cover - ultima difesa
            self.repository.update_job(
                job_id,
                status="failed",
                stage="failed",
                progress=100,
                message="Errore inatteso durante l'elaborazione.",
                error=str(exc),
            )
            logger.exception("Errore inatteso nel job %s", job_id)


def _parse_recorded_on(value: object) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
