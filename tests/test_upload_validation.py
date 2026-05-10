from __future__ import annotations

import unittest

from crd_notes.api import (
    _collect_knowledge_uploads,
    _is_allowed_knowledge_upload,
    _is_allowed_media_upload,
    _normalize_knowledge_original_name,
    _resolve_knowledge_relative_paths,
)
from crd_notes.core.errors import CrdNotesError


class UploadValidationTests(unittest.TestCase):
    def test_accepts_audio_by_mime_type(self) -> None:
        self.assertTrue(_is_allowed_media_upload("call.bin", "audio/mpeg"))

    def test_accepts_video_by_extension_when_mime_missing(self) -> None:
        self.assertTrue(_is_allowed_media_upload("screen-recording.mkv", ""))

    def test_rejects_non_media_uploads(self) -> None:
        self.assertFalse(_is_allowed_media_upload("notes.pdf", "application/pdf"))

    def test_accepts_supported_knowledge_file_extension(self) -> None:
        self.assertTrue(_is_allowed_knowledge_upload("documentazione.md"))

    def test_rejects_unsupported_knowledge_file_extension(self) -> None:
        self.assertFalse(_is_allowed_knowledge_upload("immagine.png"))

    def test_collect_knowledge_uploads_accepts_single_or_multiple(self) -> None:
        first = object()
        second = object()
        self.assertEqual(_collect_knowledge_uploads([first], None), [first])
        self.assertEqual(_collect_knowledge_uploads([first], second), [first, second])

    def test_collect_knowledge_uploads_requires_at_least_one_file(self) -> None:
        with self.assertRaises(CrdNotesError):
            _collect_knowledge_uploads(None, None)

    def test_resolve_relative_paths_defaults_to_none_when_missing(self) -> None:
        uploads = [object(), object()]
        self.assertEqual(_resolve_knowledge_relative_paths(uploads, None), [None, None])

    def test_resolve_relative_paths_requires_matching_length(self) -> None:
        uploads = [object(), object()]
        with self.assertRaises(CrdNotesError):
            _resolve_knowledge_relative_paths(uploads, ["cartella/file1.pdf"])

    def test_normalize_knowledge_original_name_supports_relative_path(self) -> None:
        normalized = _normalize_knowledge_original_name(
            filename="report.pdf",
            relative_path="documenti\\riunioni\\report.pdf",
        )
        self.assertEqual(normalized, "documenti/riunioni/report.pdf")

    def test_normalize_knowledge_original_name_rejects_traversal(self) -> None:
        with self.assertRaises(CrdNotesError):
            _normalize_knowledge_original_name(filename="report.pdf", relative_path="../segreti/report.pdf")

    def test_normalize_knowledge_original_name_uses_filename_fallback(self) -> None:
        normalized = _normalize_knowledge_original_name(filename="verbale.md", relative_path=None)
        self.assertEqual(normalized, "verbale.md")


if __name__ == "__main__":
    unittest.main()
