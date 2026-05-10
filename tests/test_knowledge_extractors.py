from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from crd_notes.core.config import AppSettings
from crd_notes.core.errors import ConfigurationError
from crd_notes.knowledge import extractors
from crd_notes.knowledge.extractors import extract_document_from_file, extract_text_from_file
from crd_notes.library.models import WorkspaceKnowledgeFile
from crd_notes.library.repository import utc_now
from crd_notes.rag.service import _chunk_knowledge_file_to_docs


class KnowledgeExtractorTests(unittest.TestCase):
    def test_text_extractor_returns_structured_document_and_compatible_text(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.md"
            path.write_text("# Titolo\n\nContenuto utile", encoding="utf-8")

            document = extract_document_from_file(path)
            text = extract_text_from_file(path)

        self.assertEqual(document.source_type, "markdown")
        self.assertIn("Contenuto utile", document.text)
        self.assertEqual(text, document.text)

    def test_csv_extractor_applies_row_limit_warning(self) -> None:
        original_limit = extractors.MAX_CSV_ROWS
        try:
            extractors.MAX_CSV_ROWS = 2
            with TemporaryDirectory() as tmp:
                path = Path(tmp) / "data.csv"
                path.write_text("a,b\nc,d\ne,f\n", encoding="utf-8")

                document = extract_document_from_file(path)
        finally:
            extractors.MAX_CSV_ROWS = original_limit

        self.assertEqual(document.source_type, "csv")
        self.assertEqual(document.row_count, 2)
        self.assertTrue(document.warnings)
        self.assertNotIn("e | f", document.text)

    def test_legacy_doc_fails_explicitly(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.doc"
            path.write_bytes(b"fake legacy word")

            with self.assertRaises(ConfigurationError) as context:
                extract_document_from_file(path)

        self.assertIn(".doc", context.exception.message)

    def test_knowledge_chunks_include_parser_metadata(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.md"
            path.write_text(" ".join(["policy"] * 80), encoding="utf-8")
            document = extract_document_from_file(path)
            knowledge_file = WorkspaceKnowledgeFile(
                id="knowledge-a",
                workspace_id="default",
                original_name="policy/prodotto/policy.md",
                stored_path=str(path),
                content_type="text/markdown",
                extension=".md",
                size_bytes=path.stat().st_size,
                sha256="hash",
                status="pending",
                error="",
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            settings = AppSettings()

            docs = _chunk_knowledge_file_to_docs(
                knowledge_file=knowledge_file,
                document=document,
                rag=settings.rag,
            )

        self.assertTrue(docs)
        self.assertEqual(docs[0].metadata["parser_source_type"], "markdown")
        self.assertEqual(docs[0].metadata["knowledge_folder"], "policy/prodotto")


if __name__ == "__main__":
    unittest.main()
