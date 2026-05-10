from __future__ import annotations

import unittest

from crd_notes.rag.chunking import chunk_text, clean_text


class RagChunkingTests(unittest.TestCase):
    def test_chunk_text_respects_size_overlap_and_offsets(self) -> None:
        text = " ".join(f"w{index}" for index in range(90))

        chunks = chunk_text(text, size=40, overlap=10)

        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0].index, 0)
        self.assertEqual(chunks[0].start_word, 0)
        self.assertEqual(chunks[0].end_word, 40)
        self.assertEqual(chunks[1].start_word, 30)
        self.assertIn("w30", chunks[1].text)

    def test_clean_text_compacts_whitespace_and_limits_length(self) -> None:
        self.assertEqual(clean_text(" alpha\n\n beta  ", limit=9), "alpha bet")


if __name__ == "__main__":
    unittest.main()
