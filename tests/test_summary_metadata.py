from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from crd_notes.library.repository import LibraryRepository
from crd_notes.library.service import LibraryService
from crd_notes.library.summary_metadata import SummaryMetadataService, parse_summary_metadata


class SummaryMetadataTests(unittest.TestCase):
    def test_parse_summary_metadata_json(self) -> None:
        parsed = parse_summary_metadata(
            """
            {
              "tags": ["requisiti", "crm"],
              "keywords": ["integrazione", "anagrafica clienti"],
              "people": ["Product Owner"],
              "topics": ["flusso onboarding"],
              "context": "La call chiarisce il perimetro funzionale."
            }
            """
        )

        self.assertEqual(parsed.tags, ["requisiti", "crm"])
        self.assertIn("integrazione", parsed.keywords)
        self.assertEqual(parsed.context, "La call chiarisce il perimetro funzionale.")

    def test_metadata_enriches_entry_search(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            library = LibraryService(repository)
            metadata_service = SummaryMetadataService(repository)
            entry = library.create_entry(
                title="Call cliente",
                notes="",
                participants=["Ada"],
                source_filename="call.mp3",
                audio_filename=None,
                duration_seconds=None,
                recorded_on=None,
                transcript="Discussione generale",
            )
            summary = library.add_summary(
                entry_id=entry.id,
                provider="ollama",
                model="llama",
                prompt_id="requisiti",
                content="Summary",
            )
            metadata_service.save_from_ai(
                summary=summary,
                raw_json='{"tags":["crm"],"keywords":["anagrafica"],"people":["Ada"],"topics":["onboarding"],"context":"Contesto"}',
            )

            by_keyword = repository.list_entries(keyword="anagrafica")
            by_query = repository.list_entries(query="onboarding")

        self.assertEqual([item.id for item in by_keyword], [entry.id])
        self.assertEqual([item.id for item in by_query], [entry.id])


if __name__ == "__main__":
    unittest.main()
