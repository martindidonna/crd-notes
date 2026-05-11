from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from crd_notes.ai.connectors.base import AiResult
from crd_notes.api import _extract_copilot_login_step, _write_upload_file_with_limit
from crd_notes.core.config import AppSettings, RagSettings, SettingsStore
from crd_notes.core.errors import ConfigurationError, CrdNotesError
from crd_notes.library.operations import OperationService
from crd_notes.library.repository import LibraryRepository
from crd_notes.library.service import LibraryService
from crd_notes.library.summary_metadata import SummaryMetadataService
from crd_notes.library.summary_workflow import SummaryWorkflowService


class _FakeAiService:
    async def summarize(self, **_kwargs):
        return AiResult(
            content="5) Azioni e responsabilita'\n- Preparare recap - Ada - 2026-05-20",
            provider="fake",
            model="fake-model",
        )

    async def complete_with_prompt(self, **_kwargs):
        return AiResult(
            content='{"tags":["meeting"],"keywords":["recap"],"people":["Ada"],"topics":["followup"],"context":"Contesto test"}',
            provider="fake",
            model="fake-model",
        )


class _FakeRagService:
    def __init__(self) -> None:
        self.indexed: list[str] = []

    def index_entry(self, entry_id: str, _settings: AppSettings) -> None:
        self.indexed.append(entry_id)


class _ChunkedUpload:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks

    async def read(self, _size: int) -> bytes:
        if not self.chunks:
            return b""
        return self.chunks.pop(0)


class RepositoryStabilityTests(unittest.TestCase):
    def test_foreign_keys_are_enforced(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            with self.assertRaises(sqlite3.IntegrityError):
                with repository.connect() as conn:
                    conn.execute(
                        """
                        insert into summaries (
                            id, entry_id, provider, model, prompt_id, content, created_at
                        )
                        values ('summary-a', 'missing-entry', 'ollama', 'llama', 'prompt', 'content', '2026-05-10T00:00:00+00:00')
                        """
                    )

    def test_entry_delete_cascades_to_summaries(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            library = LibraryService(repository)
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
                content="Summary",
            )

            with repository.connect() as conn:
                conn.execute("delete from entries where id = ?", (entry.id,))

            self.assertEqual(repository.list_summaries(entry.id), [])


class SettingsStabilityTests(unittest.TestCase):
    def test_settings_save_writes_loadable_json(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            store = SettingsStore(path)
            settings = AppSettings(whisper_model="small")

            store.save(settings)
            loaded = store.load()

            self.assertEqual(loaded.whisper_model, "small")
            self.assertFalse((Path(tmp) / ".config.json.tmp").exists())

    def test_settings_save_writes_utf8_without_bom(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            store = SettingsStore(path)

            store.save(AppSettings())

            self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_settings_load_accepts_utf8_bom_config(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_bytes(b"\xef\xbb\xbf" + b'{"whisper_model":"small"}')

            loaded = SettingsStore(path).load()

            self.assertEqual(loaded.whisper_model, "small")

    def test_settings_load_reports_invalid_json_as_configuration_error(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("{", encoding="utf-8")

            with self.assertRaises(ConfigurationError):
                SettingsStore(path).load()

    def test_rag_settings_reject_invalid_overlap(self) -> None:
        with self.assertRaises(ValidationError):
            RagSettings(chunk_size_words=80, chunk_overlap_words=80)

    def test_app_settings_reject_invalid_whisper_workers(self) -> None:
        with self.assertRaises(ValidationError):
            AppSettings(whisper_workers=0)

    def test_app_settings_reject_invalid_whisper_device(self) -> None:
        with self.assertRaises(ValidationError):
            AppSettings(whisper_device="metal")


class CopilotLoginStateTests(unittest.TestCase):
    def test_extract_copilot_login_step_reads_device_url_and_code(self) -> None:
        self.assertEqual(
            _extract_copilot_login_step("Open https://github.com/login/device and enter 12ab-34cd."),
            {
                "verification_uri": "https://github.com/login/device",
                "user_code": "12AB-34CD",
            },
        )

    def test_extract_copilot_login_step_returns_empty_fields_without_login_data(self) -> None:
        self.assertEqual(
            _extract_copilot_login_step("Waiting for GitHub authentication."),
            {"verification_uri": "", "user_code": ""},
        )


class MediaUploadLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_write_upload_file_removes_partial_file_when_too_large(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "upload.wav"
            upload = _ChunkedUpload([b"a" * 4, b"b" * 4])

            with self.assertRaises(CrdNotesError):
                await _write_upload_file_with_limit(
                    upload_file=upload,
                    target_path=target,
                    max_bytes=6,
                )

            self.assertFalse(target.exists())

    async def test_write_upload_file_accepts_file_within_limit(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "upload.wav"
            upload = _ChunkedUpload([b"a" * 4, b"b" * 4])

            await _write_upload_file_with_limit(
                upload_file=upload,
                target_path=target,
                max_bytes=8,
            )

            self.assertEqual(target.read_bytes(), b"aaaabbbb")


class SummaryWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_summary_workflow_persists_summary_metadata_operations_and_indexes(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = LibraryRepository(Path(tmp) / "library.sqlite3")
            library = LibraryService(repository)
            operations = OperationService(repository)
            metadata = SummaryMetadataService(repository)
            rag = _FakeRagService()
            workflow = SummaryWorkflowService(
                repository=repository,
                library_service=library,
                operation_service=operations,
                summary_metadata_service=metadata,
                ai_service=_FakeAiService(),
                rag_service=rag,
            )
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
            settings = AppSettings()
            settings.rag.enabled = True
            settings.rag.enrich_summaries = False

            result = await workflow.generate_for_entry(
                entry_id=entry.id,
                prompt_id="riunione_tecnica",
                settings=settings,
            )

            items = repository.list_operation_items(entry_id=entry.id)

        self.assertEqual(result.summary.provider, "fake")
        self.assertIsNotNone(result.metadata)
        self.assertEqual(result.metadata.tags, ["meeting"])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].owner, "Ada")
        self.assertEqual(rag.indexed, [entry.id])


if __name__ == "__main__":
    unittest.main()
