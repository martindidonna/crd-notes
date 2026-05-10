from __future__ import annotations

from datetime import date
from uuid import uuid4

from crd_notes.core.errors import LibraryError
from crd_notes.library.models import DEFAULT_WORKSPACE_ID, LibraryEntry, Summary, Workspace
from crd_notes.library.repository import LibraryRepository, utc_now


class LibraryService:
    def __init__(self, repository: LibraryRepository) -> None:
        self.repository = repository

    def create_entry(
        self,
        *,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        title: str,
        notes: str,
        participants: list[str],
        source_filename: str,
        audio_filename: str | None,
        duration_seconds: float | None,
        recorded_on: date | None,
        transcript: str,
    ) -> LibraryEntry:
        workspace = self.repository.get_workspace(workspace_id) or self.repository.get_workspace(
            DEFAULT_WORKSPACE_ID
        )
        if workspace is None:
            raise LibraryError("Workspace predefinito non disponibile.")
        entry = LibraryEntry(
            id=str(uuid4()),
            workspace_id=workspace.id,
            title=title.strip() or source_filename,
            notes=notes.strip(),
            participants=[item.strip() for item in participants if item.strip()],
            source_filename=source_filename,
            audio_filename=audio_filename,
            duration_seconds=duration_seconds,
            recorded_on=recorded_on,
            created_at=utc_now(),
            transcript=transcript,
        )
        self.repository.add_entry(entry)
        return entry

    def create_workspace(self, *, name: str, description: str = "") -> Workspace:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise LibraryError("Il nome del workspace e' obbligatorio.")
        now = utc_now()
        workspace = Workspace(
            id=str(uuid4()),
            name=cleaned_name,
            description=description.strip(),
            is_default=False,
            created_at=now,
            updated_at=now,
        )
        self.repository.add_workspace(workspace)
        return workspace

    def add_summary(
        self,
        *,
        entry_id: str,
        provider: str,
        model: str,
        prompt_id: str,
        content: str,
    ) -> Summary:
        if self.repository.get_entry(entry_id) is None:
            raise LibraryError("Trascrizione non trovata.")

        summary = Summary(
            id=str(uuid4()),
            entry_id=entry_id,
            provider=provider,
            model=model,
            prompt_id=prompt_id,
            content=content,
            created_at=utc_now(),
        )
        self.repository.add_summary(summary)
        return summary
