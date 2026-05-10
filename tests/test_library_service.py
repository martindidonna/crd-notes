from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from crd_notes.library.repository import LibraryRepository
from crd_notes.library.service import LibraryService


class LibraryServiceTests(unittest.TestCase):
    def test_create_entry_persists_recorded_on(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            service = LibraryService(repository)

            entry = service.create_entry(
                title="Riunione prodotto",
                notes="",
                participants=["Ada"],
                source_filename="riunione.mp3",
                audio_filename="riunione.wav",
                duration_seconds=120.0,
                recorded_on=date(2026, 5, 9),
                transcript="Trascrizione",
            )

            saved = repository.get_entry(entry.id)

        self.assertIsNotNone(saved)
        assert saved is not None
        self.assertEqual(saved.recorded_on, date(2026, 5, 9))


if __name__ == "__main__":
    unittest.main()
