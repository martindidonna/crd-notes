from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from crd_notes.library.operations import OperationService, parse_ai_operations, parse_summary_operations
from crd_notes.library.repository import LibraryRepository
from crd_notes.library.service import LibraryService


class OperationRepositoryTests(unittest.TestCase):
    def test_extract_persists_operation_items_and_counts(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            library = LibraryService(repository)
            operations = OperationService(repository)
            workspace = library.create_workspace(name="Cliente Alpha")
            entry = library.create_entry(
                workspace_id=workspace.id,
                title="Riunione prodotto",
                notes="",
                participants=["Ada"],
                source_filename="meeting.mp3",
                audio_filename="meeting.wav",
                duration_seconds=90.0,
                recorded_on=date(2026, 5, 9),
                transcript="Trascrizione",
            )
            library.add_summary(
                entry_id=entry.id,
                provider="ollama",
                model="llama",
                prompt_id="requisiti",
                content="""
4) Decisioni prese
- Decisione: procedere con la dashboard operativa

5) Azioni e responsabilita'
- [Preparare wireframe] - [Ada] - [2026-05-20] - [Stato: definita]

6) Rischi, blocchi e domande aperte
- Rischio: manca conferma sul modello AI
- Chiarimento necessario: chi valida l'output?
""",
            )

            first = operations.extract_from_latest_summary(entry.id)
            second = operations.extract_from_latest_summary(entry.id)
            counts = repository.library_counts()[entry.id]
            visible = repository.list_operation_items(workspace_id=workspace.id)

        self.assertEqual(len(first), len(second))
        self.assertEqual(len(visible), len(first))
        self.assertEqual(counts["summary_count"], 1)
        self.assertEqual(counts["operation_total_count"], 4)
        self.assertEqual(counts["operation_open_count"], 4)
        action = next(item for item in first if item.kind == "action")
        self.assertEqual(action.owner, "Ada")
        self.assertEqual(action.due_date, date(2026, 5, 20))

    def test_update_and_delete_operation_item(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            library = LibraryService(repository)
            operations = OperationService(repository)
            entry = library.create_entry(
                title="Riunione",
                notes="",
                participants=[],
                source_filename="meeting.mp3",
                audio_filename=None,
                duration_seconds=None,
                recorded_on=None,
                transcript="Trascrizione",
            )
            library.add_summary(
                entry_id=entry.id,
                provider="ollama",
                model="llama",
                prompt_id="sintesi_generale",
                content="3) Decisioni prese\n- Decisione: approvato",
            )
            item = operations.extract_from_latest_summary(entry.id)[0]

            updated = operations.update_item(item.id, status="done", owner="Ada")
            repository.delete_operation_item(item.id)
            deleted = repository.get_operation_item(item.id)

        self.assertEqual(updated.status, "done")
        self.assertEqual(updated.owner, "Ada")
        self.assertIsNone(deleted)


class OperationParserTests(unittest.TestCase):
    def test_parse_sections_and_action_pattern(self) -> None:
        items = parse_summary_operations(
            """
6) Decisioni prese
- Decisione: usare SQLite locale
7) Piano operativo
- [Creare migrazione] - [Marco] - [2026-05-18] - [Dipendenze]
8) Rischi, blocchi e domande aperte
- Rischio: trascrizione ambigua
- Domanda: chi approva?
"""
        )

        self.assertEqual([item.kind for item in items], ["decision", "action", "risk", "question"])
        self.assertEqual(items[1].owner, "Marco")
        self.assertEqual(items[1].due_date, date(2026, 5, 18))

    def test_parse_ai_json(self) -> None:
        items = parse_ai_operations(
            '{"items":[{"kind":"action","text":"Inviare recap","owner":"Ada","due_date":"2026-05-21"}]}'
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].kind, "action")
        self.assertEqual(items[0].due_date, date(2026, 5, 21))


if __name__ == "__main__":
    unittest.main()
