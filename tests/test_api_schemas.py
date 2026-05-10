from __future__ import annotations

import unittest
from datetime import datetime, timezone

from crd_notes.schemas import ChatMessageCreateRequest, LibraryEntryListResponse


class ApiSchemaTests(unittest.TestCase):
    def test_list_defaults_are_not_shared_between_instances(self) -> None:
        first = ChatMessageCreateRequest(content="A")
        second = ChatMessageCreateRequest(content="B")

        first.mentioned_entry_ids.append("entry-a")

        self.assertEqual(second.mentioned_entry_ids, [])

    def test_response_list_defaults_are_not_shared_between_instances(self) -> None:
        now = datetime.now(timezone.utc)
        first = LibraryEntryListResponse(
            id="entry-a",
            workspace_id="default",
            title="A",
            notes="",
            participants=[],
            source_filename="a.mp3",
            audio_filename=None,
            duration_seconds=None,
            created_at=now,
        )
        second = LibraryEntryListResponse(
            id="entry-b",
            workspace_id="default",
            title="B",
            notes="",
            participants=[],
            source_filename="b.mp3",
            audio_filename=None,
            duration_seconds=None,
            created_at=now,
        )

        first.tags.append("roadmap")

        self.assertEqual(second.tags, [])


if __name__ == "__main__":
    unittest.main()
