from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from crd_notes.ai.connectors.base import AiResult
from crd_notes.chat.context import clean_assistant_content, compact_chunks, compact_history
from crd_notes.chat.service import WorkspaceChatService
from crd_notes.core.config import AppSettings
from crd_notes.library.models import ChatMessage
from crd_notes.library.repository import LibraryRepository, utc_now
from crd_notes.library.service import LibraryService
from crd_notes.rag.service import RagChunk, RagContext


class _FakeRagService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def build_context(self, **kwargs):
        self.calls.append(kwargs)
        return RagContext(
            chunks=[
                RagChunk(
                    text="Decisione: confermare piano rilasci.",
                    score=0.9,
                    entry_id=(kwargs.get("entry_ids") or ["entry-a"])[0],
                    entry_title="Riunione roadmap",
                    doc_type="summary",
                    source="riassunto",
                )
            ],
            context_text="- [summary | Riunione roadmap | riassunto] Decisione: confermare piano rilasci.",
        )


class _SequencedRagService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def build_context(self, **kwargs):
        self.calls.append(kwargs)
        folder = (kwargs.get("knowledge_folders") or [""])[0]
        return RagContext(
            chunks=[
                RagChunk(
                    text=f"Contenuto folder {folder}",
                    score=0.8,
                    entry_id="knowledge-a",
                    entry_title="policy.md",
                    doc_type="knowledge_file",
                    source=f"{folder}/policy.md",
                )
            ],
            context_text=f"- [knowledge_file | policy.md | {folder}/policy.md] Contenuto folder {folder}",
        )


class _FakeAiService:
    async def complete_with_prompt(self, **kwargs):
        return AiResult(content="Risposta basata sul RAG.", provider="ollama", model="llama3")


class _CapturingAiService:
    def __init__(self) -> None:
        self.last_kwargs: dict | None = None

    async def complete_with_prompt(self, **kwargs):
        self.last_kwargs = kwargs
        return AiResult(content="Risposta basata sul RAG.", provider="ollama", model="llama3")


class WorkspaceChatServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_message_passes_question_and_rag_context_to_ai_prompt(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            library = LibraryService(repository)
            entry = library.create_entry(
                title="Riunione roadmap",
                notes="",
                participants=["Ada"],
                source_filename="roadmap.mp3",
                audio_filename=None,
                duration_seconds=120,
                recorded_on=date(2026, 5, 9),
                transcript="Trascrizione roadmap",
            )
            rag = _FakeRagService()
            ai = _CapturingAiService()
            service = WorkspaceChatService(
                repository=repository,
                rag_service=rag,
                ai_service=ai,
            )

            await service.send_message(
                thread_id=None,
                workspace_id="default",
                content="chi e' zinaj?",
                mentioned_entry_ids=[entry.id],
                mentioned_knowledge_folders=[],
                settings=AppSettings(),
                provider="ollama",
                model="llama3",
            )

        self.assertIsNotNone(ai.last_kwargs)
        input_text = ai.last_kwargs["input_text"]
        self.assertIn("chi e' zinaj?", input_text)
        self.assertIn("Materiale del workspace:", input_text)
        self.assertIn("Decisione: confermare piano rilasci.", input_text)
        self.assertNotIn("score=", input_text)

    async def test_send_message_persists_turn_and_sources(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            library = LibraryService(repository)
            entry = library.create_entry(
                title="Riunione roadmap",
                notes="",
                participants=["Ada"],
                source_filename="roadmap.mp3",
                audio_filename=None,
                duration_seconds=120,
                recorded_on=date(2026, 5, 9),
                transcript="Trascrizione roadmap",
            )
            rag = _FakeRagService()
            service = WorkspaceChatService(
                repository=repository,
                rag_service=rag,
                ai_service=_FakeAiService(),
            )

            turn = await service.send_message(
                thread_id=None,
                workspace_id="default",
                content="Cosa abbiamo deciso?",
                mentioned_entry_ids=[entry.id],
                mentioned_knowledge_folders=[],
                settings=AppSettings(),
                provider="ollama",
                model="llama3",
            )
            messages = repository.list_chat_messages(turn.thread.id)
            sources = repository.list_chat_message_sources(turn.assistant_message.id)

        self.assertEqual(turn.thread.workspace_id, "default")
        self.assertEqual([message.role for message in messages], ["user", "assistant"])
        self.assertEqual(sources[0].entry_id, entry.id)
        self.assertEqual(rag.calls[0]["entry_ids"], [entry.id])

    async def test_hash_folder_limits_retrieval_to_selected_knowledge_folder(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            rag = _SequencedRagService()
            service = WorkspaceChatService(
                repository=repository,
                rag_service=rag,
                ai_service=_FakeAiService(),
            )

            await service.send_message(
                thread_id=None,
                workspace_id="default",
                content="Quali policy valgono?",
                mentioned_entry_ids=[],
                mentioned_knowledge_folders=["policy/prodotto"],
                settings=AppSettings(),
                provider="ollama",
                model="llama3",
            )

        self.assertEqual(len(rag.calls), 1)
        self.assertEqual(rag.calls[0]["doc_types"], ["knowledge_file"])
        self.assertEqual(rag.calls[0]["knowledge_folders"], ["policy/prodotto"])

    def test_compact_chunks_deduplicates_and_respects_budget(self) -> None:
        chunks = [
            RagChunk(" ".join(["alpha"] * 120), 0.9, "e1", "Call A", "summary", "riassunto"),
            RagChunk(" ".join(["alpha"] * 120), 0.8, "e1", "Call A", "summary", "riassunto"),
            RagChunk("beta", 0.01, "e2", "Call B", "summary", "riassunto"),
            RagChunk("gamma utile", 0.7, "e3", "Call C", "metadata", "metadati"),
        ]

        compacted = compact_chunks(chunks, max_chars=760)

        self.assertEqual(len(compacted.chunks), 2)
        self.assertLessEqual(len(compacted.text), 760)
        self.assertTrue(compacted.evidence)
        self.assertNotIn("beta", compacted.text)
        self.assertNotIn("score=", compacted.text)
        self.assertNotIn(" | ", compacted.text)

    def test_clean_assistant_content_normalizes_rag_artifacts(self) -> None:
        content = clean_assistant_content(
            "Supportato dal RAG: Zinaj e' il quarto Sankto.<br>"
            "Incerto: non ci sono altri dettagli nel RAG #4."
        )

        self.assertIn("Zinaj e' il quarto Sankto.", content)
        self.assertIn("non ci sono altri dettagli", content)
        self.assertNotIn("<br>", content)
        self.assertNotIn("Supportato dal RAG", content)
        self.assertNotIn("RAG #4", content)

    def test_compact_history_keeps_recent_messages_under_budget(self) -> None:
        messages = [
            ChatMessage(
                str(index),
                "t1",
                "assistant" if index % 2 else "user",
                "meta assistant" if index % 2 else "x" * 600,
                "",
                "",
                utc_now(),
            )
            for index in range(10)
        ]

        history = compact_history(messages)

        self.assertLessEqual(len(history), 1400)
        self.assertNotIn("meta assistant", history)


if __name__ == "__main__":
    unittest.main()
