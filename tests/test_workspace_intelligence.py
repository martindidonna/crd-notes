from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from crd_notes.library.models import OperationItem
from crd_notes.library.repository import LibraryRepository, utc_now
from crd_notes.library.service import LibraryService
from crd_notes.library.summary_metadata import SummaryMetadataService
from crd_notes.library.workspace_intelligence import WorkspaceIntelligenceService


class WorkspaceIntelligenceTests(unittest.TestCase):
    def test_builds_local_workspace_intelligence(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            library = LibraryService(repository)
            metadata_service = SummaryMetadataService(repository)
            intelligence_service = WorkspaceIntelligenceService(repository)
            workspace = library.create_workspace(name="Cliente Alfa")
            entry = library.create_entry(
                workspace_id=workspace.id,
                title="Roadmap onboarding",
                notes="CRM e import anagrafiche",
                participants=["Ada"],
                source_filename="call.mp3",
                audio_filename=None,
                duration_seconds=None,
                recorded_on=None,
                transcript="Discussione su onboarding clienti e migrazione CRM.",
            )
            summary = library.add_summary(
                entry_id=entry.id,
                provider="ollama",
                model="llama",
                prompt_id="riunione_tecnica",
                content="Decisione: usare import incrementale. Rischio: dati duplicati.",
            )
            metadata_service.save_from_ai(
                summary=summary,
                raw_json='{"tags":["crm","onboarding"],"keywords":["anagrafica clienti"],"people":["Ada"],"topics":["migrazione dati"],"context":"Contesto cliente."}',
            )
            repository.add_operation_item(
                OperationItem(
                    id="decision-1",
                    entry_id=entry.id,
                    summary_id=summary.id,
                    kind="decision",
                    text="Usare import incrementale",
                    owner="",
                    due_date=None,
                    status="open",
                    source="summary",
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
            )

            intelligence = intelligence_service.build(workspace.id)

        self.assertEqual(intelligence.entry_count, 1)
        self.assertEqual(intelligence.summary_count, 1)
        self.assertEqual(intelligence.top_tags[0].text, "crm")
        self.assertEqual(intelligence.top_people[0].text, "ada")
        self.assertEqual(intelligence.decisions[0].text, "Usare import incrementale")
        self.assertTrue(intelligence.clusters)


if __name__ == "__main__":
    unittest.main()
