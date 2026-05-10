from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from crd_notes.api import ai_extract_operations, extract_operations, list_operations, update_operation
from crd_notes.core.config import AppSettings
from crd_notes.library.operations import OperationService
from crd_notes.library.repository import LibraryRepository
from crd_notes.library.service import LibraryService
from crd_notes.schemas import OperationItemUpdateRequest


class FakeSettingsStore:
    def load(self) -> AppSettings:
        return AppSettings()


class FakeAiService:
    async def complete_with_prompt(self, **_kwargs):
        class Result:
            content = '{"items":[{"kind":"decision","text":"Validare la V1","owner":"","due_date":null}]}'

        return Result()


class OperationApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.repository = LibraryRepository(Path(self.tmp.name) / "library.sqlite3")
        self.library = LibraryService(self.repository)
        self.operations = OperationService(self.repository)
        self.entry = self.library.create_entry(
            title="Call operativa",
            notes="",
            participants=["Ada"],
            source_filename="call.mp3",
            audio_filename="call.wav",
            duration_seconds=120.0,
            recorded_on=date(2026, 5, 9),
            transcript="Trascrizione",
        )
        self.library.add_summary(
            entry_id=self.entry.id,
            provider="ollama",
            model="llama",
            prompt_id="sintesi_generale",
            content="3) Decisioni prese\n- Decisione: partire dalla V1\n4) Azioni e responsabilita'\n- [Scrivere test] - [Ada] - [2026-05-22]",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    async def test_list_and_update_operations(self) -> None:
        extract_operations(self.entry.id, self.repository, self.operations)
        items = list_operations(self.repository)

        updated = update_operation(
            items[0].id,
            OperationItemUpdateRequest(status="done"),
            self.repository,
            self.operations,
        )

        self.assertEqual(len(items), 2)
        self.assertEqual(updated.status, "done")

    async def test_ai_extract_replaces_ai_items_from_valid_json(self) -> None:
        response = await ai_extract_operations(
            self.entry.id,
            self.repository,
            self.operations,
            FakeSettingsStore(),
            FakeAiService(),
        )

        self.assertEqual(len(response.items), 1)
        self.assertEqual(response.items[0].kind, "decision")
        self.assertEqual(response.items[0].source, "ai")


if __name__ == "__main__":
    unittest.main()
