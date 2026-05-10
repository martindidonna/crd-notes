from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from crd_notes.library.models import DEFAULT_WORKSPACE_ID
from crd_notes.library.repository import LibraryRepository
from crd_notes.library.service import LibraryService


class WorkspaceTests(unittest.TestCase):
    def test_repository_creates_default_workspace(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            workspaces = repository.list_workspaces()

        self.assertEqual(workspaces[0].id, DEFAULT_WORKSPACE_ID)
        self.assertTrue(workspaces[0].is_default)

    def test_entries_are_scoped_by_workspace(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            service = LibraryService(repository)
            workspace = service.create_workspace(name="Cliente Alpha")
            generic = service.create_entry(
                title="Generica",
                notes="",
                participants=[],
                source_filename="generic.mp3",
                audio_filename=None,
                duration_seconds=None,
                recorded_on=None,
                transcript="Trascrizione generica",
            )
            scoped = service.create_entry(
                workspace_id=workspace.id,
                title="Alpha",
                notes="",
                participants=["Ada"],
                source_filename="alpha.mp3",
                audio_filename=None,
                duration_seconds=30.0,
                recorded_on=date(2026, 5, 9),
                transcript="Trascrizione alpha",
            )

            generic_entries = repository.list_entries(DEFAULT_WORKSPACE_ID)
            scoped_entries = repository.list_entries(workspace.id)

        self.assertEqual([entry.id for entry in generic_entries], [generic.id])
        self.assertEqual([entry.id for entry in scoped_entries], [scoped.id])
        self.assertEqual(scoped_entries[0].workspace_id, workspace.id)


if __name__ == "__main__":
    unittest.main()
