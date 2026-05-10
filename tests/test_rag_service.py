from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from crd_notes.core.config import AppSettings
from crd_notes.library.models import OperationItem, WorkspaceKnowledgeFile
from crd_notes.library.repository import LibraryRepository, utc_now
from crd_notes.library.service import LibraryService
from crd_notes.library.summary_metadata import SummaryMetadataService
from crd_notes.rag.service import RagService


class _FakeCollection:
    def __init__(self) -> None:
        self.deleted_where: list[dict] = []
        self.add_calls: list[dict] = []
        self.query_args: list[dict] = []
        self.query_result: dict = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

    def delete(self, *, where: dict) -> None:
        self.deleted_where.append(where)

    def add(self, **kwargs) -> None:
        self.add_calls.append(kwargs)

    def query(self, **kwargs):
        self.query_args.append(kwargs)
        return self.query_result


class RagServiceTests(unittest.TestCase):
    def test_index_entry_adds_expected_documents(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            library = LibraryService(repository)
            metadata_service = SummaryMetadataService(repository)
            entry = library.create_entry(
                title="Riunione roadmap",
                notes="Allineamento trimestrale.",
                participants=["Ada", "Luca"],
                source_filename="roadmap.mp3",
                audio_filename=None,
                duration_seconds=1800,
                recorded_on=date(2026, 5, 1),
                transcript=" ".join(["roadmap"] * 220),
            )
            summary = library.add_summary(
                entry_id=entry.id,
                provider="ollama",
                model="llama3",
                prompt_id="riunione_tecnica",
                content="Definite priorita', rischi e dipendenze.",
            )
            metadata_service.save_from_ai(
                summary=summary,
                raw_json='{"tags":["roadmap"],"keywords":["priorita"],"people":["Ada"],"topics":["rilascio"],"context":"Piano Q3"}',
            )
            repository.add_operation_item(
                OperationItem(
                    id=str(uuid4()),
                    entry_id=entry.id,
                    summary_id=summary.id,
                    kind="action",
                    text="Confermare piano rilasci.",
                    owner="Luca",
                    due_date=date(2026, 5, 15),
                    status="open",
                    source="manual",
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
            )

            service = RagService(repository)
            collection = _FakeCollection()
            service._collection = lambda workspace_id, rag: collection
            service._embed_documents = lambda texts, rag: [[0.1, 0.2]] * len(texts)

            settings = AppSettings()
            settings.rag.enabled = True
            service.index_entry(entry.id, settings)

        self.assertEqual(collection.deleted_where, [{"entry_id": entry.id}])
        self.assertEqual(len(collection.add_calls), 1)
        payload = collection.add_calls[0]
        self.assertEqual(len(payload["documents"]), len(payload["ids"]))
        metadata_types = {item["doc_type"] for item in payload["metadatas"]}
        self.assertTrue({"transcript", "summary", "metadata", "operation", "note"}.issubset(metadata_types))

    def test_build_context_uses_doc_type_filter_and_context_limit(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            service = RagService(repository)
            collection = _FakeCollection()
            collection.query_result = {
                "documents": [["Primo contesto utile", "Secondo contesto"]],
                "metadatas": [[
                    {
                        "entry_id": "e1",
                        "entry_title": "Call A",
                        "doc_type": "summary",
                        "source": "riassunto",
                    },
                    {
                        "entry_id": "e2",
                        "entry_title": "Call B",
                        "doc_type": "metadata",
                        "source": "metadati summary",
                    },
                ]],
                "distances": [[0.1, 0.3]],
            }
            service._collection = lambda workspace_id, rag: collection
            service._embed_query = lambda text, rag: [0.4, 0.5]

            settings = AppSettings()
            settings.rag.enabled = True
            settings.rag.max_context_chars = 90
            context = service.build_context(
                workspace_id="default",
                query_text="roadmap trimestrale",
                settings=settings,
                doc_types=["summary", "metadata"],
                top_k=2,
            )

        self.assertEqual(len(collection.query_args), 1)
        self.assertEqual(collection.query_args[0]["where"], {"doc_type": {"$in": ["summary", "metadata"]}})
        self.assertTrue(context.chunks)
        self.assertLessEqual(len(context.context_text), settings.rag.max_context_chars)

    def test_build_context_adds_keyword_results_and_reranks(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            service = RagService(repository)
            collection = _FakeCollection()
            collection.query_result = {
                "documents": [["Contesto vettoriale"]],
                "metadatas": [[
                    {
                        "entry_id": "e1",
                        "entry_title": "Call A",
                        "doc_type": "summary",
                        "source": "riassunto",
                    },
                ]],
                "distances": [[0.2]],
            }
            service._collection = lambda workspace_id, rag: collection
            service._embed_query = lambda text, rag: [0.4, 0.5]
            service._rerank_chunks = lambda query_text, chunks, settings: sorted(
                chunks,
                key=lambda chunk: chunk.text,
            )
            repository.search_rag_keyword_docs = lambda **kwargs: [
                {
                    "content": "Contesto keyword",
                    "rank": -0.2,
                    "entry_id": "e2",
                    "entry_title": "Call B",
                    "doc_type": "metadata",
                    "source": "metadati",
                }
            ]

            settings = AppSettings()
            settings.rag.enabled = True
            settings.rag.hybrid_keyword_enabled = True
            context = service.build_context(
                workspace_id="default",
                query_text="roadmap trimestrale",
                settings=settings,
                top_k=4,
            )

        self.assertEqual(len(context.chunks), 2)
        self.assertEqual({chunk.text for chunk in context.chunks}, {"Contesto keyword", "Contesto vettoriale"})

    def test_build_context_combines_doc_type_and_entry_filters(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            service = RagService(repository)
            collection = _FakeCollection()
            service._collection = lambda workspace_id, rag: collection
            service._embed_query = lambda text, rag: [0.4, 0.5]

            settings = AppSettings()
            settings.rag.enabled = True
            service.build_context(
                workspace_id="default",
                query_text="decisioni roadmap",
                settings=settings,
                doc_types=["summary"],
                entry_ids=["entry-a", "entry-b"],
                knowledge_folders=["policy/prodotto"],
            )

        self.assertEqual(
            collection.query_args[0]["where"],
            {
                "$and": [
                    {"doc_type": {"$in": ["summary"]}},
                    {"entry_id": {"$in": ["entry-a", "entry-b"]}},
                    {"knowledge_folder": {"$in": ["policy/prodotto"]}},
                ]
            },
        )

    def test_index_workspace_knowledge_file_adds_chunks_and_sets_status_indexed(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            knowledge_path = Path(tmp) / "knowledge.txt"
            knowledge_path.write_text(" ".join(["policy"] * 220), encoding="utf-8")

            knowledge_file = WorkspaceKnowledgeFile(
                id=str(uuid4()),
                workspace_id="default",
                original_name="policy/prodotto/policy.txt",
                stored_path=str(knowledge_path),
                content_type="text/plain",
                extension=".txt",
                size_bytes=knowledge_path.stat().st_size,
                sha256="hash-demo",
                status="pending",
                error="",
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            repository.add_workspace_knowledge_file(knowledge_file)

            service = RagService(repository)
            collection = _FakeCollection()
            service._collection = lambda workspace_id, rag: collection
            service._embed_documents = lambda texts, rag: [[0.1, 0.2]] * len(texts)

            settings = AppSettings()
            settings.rag.enabled = True
            service.index_workspace_knowledge_file(knowledge_file.id, settings)

            refreshed = repository.get_workspace_knowledge_file(knowledge_file.id)

        self.assertEqual(collection.deleted_where, [{"knowledge_file_id": knowledge_file.id}])
        self.assertEqual(len(collection.add_calls), 1)
        payload = collection.add_calls[0]
        metadata_types = {item["doc_type"] for item in payload["metadatas"]}
        self.assertIn("knowledge_file", metadata_types)
        self.assertIn("policy/prodotto", {item["knowledge_folder"] for item in payload["metadatas"]})
        self.assertIsNotNone(refreshed)
        self.assertEqual(refreshed.status, "indexed")

    def test_index_workspace_knowledge_file_does_not_delete_vector_docs_before_embedding(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            knowledge_path = Path(tmp) / "knowledge.txt"
            knowledge_path.write_text(" ".join(["policy"] * 80), encoding="utf-8")

            knowledge_file = WorkspaceKnowledgeFile(
                id=str(uuid4()),
                workspace_id="default",
                original_name="policy.txt",
                stored_path=str(knowledge_path),
                content_type="text/plain",
                extension=".txt",
                size_bytes=knowledge_path.stat().st_size,
                sha256="hash-demo",
                status="indexed",
                error="",
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            repository.add_workspace_knowledge_file(knowledge_file)

            service = RagService(repository)
            collection = _FakeCollection()
            service._collection = lambda workspace_id, rag: collection

            def fail_embed(texts, rag):
                raise RuntimeError("embedding unavailable")

            service._embed_documents = fail_embed
            settings = AppSettings()
            settings.rag.enabled = True
            service.index_workspace_knowledge_file(knowledge_file.id, settings)

            refreshed = repository.get_workspace_knowledge_file(knowledge_file.id)

        self.assertEqual(collection.deleted_where, [])
        self.assertEqual(collection.add_calls, [])
        self.assertIsNotNone(refreshed)
        self.assertEqual(refreshed.status, "failed")


if __name__ == "__main__":
    unittest.main()
