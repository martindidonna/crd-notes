from __future__ import annotations

import unittest
from pathlib import Path

from crd_notes.core.errors import TranscriptionError
from crd_notes.transcription.whisper import WhisperTranscriber


class _FakeSegment:
    def __init__(self, text: str, end: float) -> None:
        self.text = text
        self.end = end


class _FakeInfo:
    def __init__(self, duration: float) -> None:
        self.duration = duration


class _FakeModel:
    def __init__(self, segments: list[_FakeSegment], duration: float = 30.0) -> None:
        self._segments = segments
        self._info = _FakeInfo(duration)

    def transcribe(self, *_args, **_kwargs):
        return iter(self._segments), self._info


class _TestWhisperTranscriber(WhisperTranscriber):
    def __init__(self, model: _FakeModel) -> None:
        super().__init__()
        self._model = model

    def _get_model(self, *_args, **_kwargs) -> object:
        return self._model


class _CapturingWhisperTranscriber(WhisperTranscriber):
    def __init__(self) -> None:
        super().__init__()
        self.kwargs: dict[str, object] = {}

    def _get_model(self, *_args, **kwargs) -> object:
        self.kwargs = kwargs
        return _FakeModel([_FakeSegment("ok", 1)], duration=1)


class WhisperTranscriberTests(unittest.TestCase):
    def test_transcribe_removes_known_bias_lines_for_italian(self) -> None:
        model = _FakeModel(
            [
                _FakeSegment("Discussione progetto.", 10),
                _FakeSegment("Sottotitoli creati dalla comunità Amara.org", 20),
                _FakeSegment("Decisioni finali.", 30),
            ]
        )
        transcriber = _TestWhisperTranscriber(model)

        transcript = transcriber.transcribe(
            Path("fake.wav"),
            model_name="tiny",
            language="it",
        )

        self.assertEqual(transcript, "Discussione progetto.\nDecisioni finali.")

    def test_transcribe_removes_known_english_bias_lines_when_language_is_italian(self) -> None:
        model = _FakeModel(
            [
                _FakeSegment("Roadmap update", 8),
                _FakeSegment("Subtitles by the Amara.org community", 16),
                _FakeSegment("Action items", 24),
            ]
        )
        transcriber = _TestWhisperTranscriber(model)

        transcript = transcriber.transcribe(
            Path("fake.wav"),
            model_name="tiny",
            language="it",
        )

        self.assertEqual(transcript, "Roadmap update\nAction items")

    def test_transcribe_raises_when_only_bias_lines_remain(self) -> None:
        model = _FakeModel(
            [
                _FakeSegment("Sottotitoli a cura di QTSS", 10),
                _FakeSegment("Sottotitoli e revisione a cura di QTSS.", 20),
            ]
        )
        transcriber = _TestWhisperTranscriber(model)

        with self.assertRaises(TranscriptionError):
            transcriber.transcribe(
                Path("fake.wav"),
                model_name="tiny",
                language="it",
            )

    def test_transcribe_does_not_filter_for_non_italian_language(self) -> None:
        model = _FakeModel(
            [
                _FakeSegment("Sottotitoli creati dalla comunità Amara.org", 10),
            ]
        )
        transcriber = _TestWhisperTranscriber(model)

        transcript = transcriber.transcribe(
            Path("fake.wav"),
            model_name="tiny",
            language="en",
        )

        self.assertEqual(transcript, "Sottotitoli creati dalla comunità Amara.org")

    def test_transcribe_passes_device_to_model_loader(self) -> None:
        transcriber = _CapturingWhisperTranscriber()

        transcriber.transcribe(Path("fake.wav"), model_name="tiny", device="cuda")

        self.assertEqual(transcriber.kwargs["device"], "cuda")


if __name__ == "__main__":
    unittest.main()
