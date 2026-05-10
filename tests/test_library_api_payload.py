from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from crd_notes.api import list_library, read_entry
from crd_notes.library.repository import LibraryRepository
from crd_notes.library.service import LibraryService


class LibraryApiPayloadTests(unittest.TestCase):
    def test_library_list_omits_transcript_until_detail_is_requested(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            service = LibraryService(repository)
            entry = service.create_entry(
                title="Riunione",
                notes="",
                participants=[],
                source_filename="call.mp3",
                audio_filename=None,
                duration_seconds=None,
                recorded_on=None,
                transcript="Testo lungo della trascrizione",
            )

            items = list_library(repository)
            detail = read_entry(entry.id, repository)

        self.assertFalse(hasattr(items[0], "transcript"))
        self.assertEqual(detail.entry.transcript, "Testo lungo della trascrizione")


if __name__ == "__main__":
    unittest.main()
