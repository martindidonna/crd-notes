from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from crd_notes.core.errors import TranscriptionError

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, str], None]


def _normalize_bias_text(text: str) -> str:
    normalized = " ".join(text.strip().casefold().split())
    return normalized.strip(" .,!?:;")


_WHISPER_BIAS_TEXTS_BY_LANGUAGE: dict[str, frozenset[str]] = {
    "it": frozenset(
        _normalize_bias_text(text)
        for text in [
            "Sottotitoli creati dalla comunità Amara.org",
            "Sottotitoli di Sottotitoli di Amara.org",
            "Sottotitoli e revisione al canale di Amara.org",
            "Sottotitoli e revisione a cura di Amara.org",
            "Sottotitoli e revisione a cura di QTSS",
            "Sottotitoli e revisione a cura di QTSS.",
            "Sottotitoli a cura di QTSS",
            "Subtitles by the Amara.org community",
            "Subtitles by Amara.org community",
        ]
    )
}


class WhisperTranscriber:
    def __init__(self) -> None:
        self._models: dict[tuple[str, str, int, int], object] = {}

    def transcribe(
        self,
        audio_path: Path,
        *,
        model_name: str,
        language: str = "it",
        device: str = "cpu",
        compute_type: str = "int8",
        beam_size: int = 1,
        cpu_threads: int = 0,
        workers: int = 1,
        vad_filter: bool = True,
        condition_on_previous_text: bool = False,
        duration_seconds: float | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> str:
        model = self._get_model(
            model_name,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
            workers=workers,
        )
        try:
            segments, info = model.transcribe(
                str(audio_path),
                language=language,
                vad_filter=vad_filter,
                beam_size=max(1, beam_size),
                best_of=1,
                condition_on_previous_text=condition_on_previous_text,
                word_timestamps=False,
            )
            total_duration = duration_seconds or getattr(info, "duration", None)
            started_at = time.monotonic()
            last_update = 0.0
            last_progress = 0
            lines = []
            for segment in segments:
                text = segment.text.strip()
                if text and not self._is_whisper_bias_text(text, language=language):
                    lines.append(text)
                if on_progress and total_duration:
                    progress = min(99, max(1, int((segment.end / total_duration) * 100)))
                    now = time.monotonic()
                    if progress > last_progress or now - last_update >= 3:
                        last_progress = progress
                        last_update = now
                        on_progress(
                            progress,
                            self._progress_message(segment.end, total_duration, started_at),
                        )
        except Exception as exc:
            raise TranscriptionError(
                "Trascrizione non riuscita.",
                detail=str(exc),
            ) from exc

        transcript = "\n".join(lines).strip()
        if not transcript:
            raise TranscriptionError("Whisper non ha prodotto testo utile.")
        return transcript

    def _is_whisper_bias_text(self, text: str, *, language: str) -> bool:
        language_code = (language or "").strip().lower()
        known_bias_texts = _WHISPER_BIAS_TEXTS_BY_LANGUAGE.get(language_code)
        if not known_bias_texts:
            return False
        return _normalize_bias_text(text) in known_bias_texts

    def _get_model(
        self,
        model_name: str,
        *,
        device: str,
        compute_type: str,
        cpu_threads: int,
        workers: int,
    ) -> object:
        resolved_device = "cuda" if device == "cuda" else "cpu"
        resolved_compute_type = "int8" if resolved_device == "cpu" and compute_type == "float16" else compute_type
        model_key = (model_name, resolved_device, resolved_compute_type, cpu_threads, workers)
        if model_key in self._models:
            return self._models[model_key]

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            missing = getattr(exc, "name", None)
            if missing and missing != "faster_whisper":
                raise TranscriptionError(
                    f"Dipendenza mancante per Whisper: {missing}. Avvia scripts/crd-notes-starter.ps1 per aggiornare l'ambiente.",
                    detail=str(exc),
                ) from exc
            raise TranscriptionError(
                "faster-whisper non e' installato. Avvia l'applicazione tramite scripts/crd-notes-starter.ps1.",
                detail=str(exc),
            ) from exc

        logger.info("Caricamento modello Whisper: %s", model_name)
        try:
            model = WhisperModel(
                model_name,
                device=resolved_device,
                compute_type=resolved_compute_type,
                cpu_threads=cpu_threads,
                num_workers=workers,
            )
        except Exception as exc:
            if resolved_device == "cuda":
                logger.warning(
                    "Caricamento modello Whisper su CUDA non riuscito, riprovo su CPU: %s",
                    exc,
                )
                try:
                    model = WhisperModel(
                        model_name,
                        device="cpu",
                        compute_type="int8",
                        cpu_threads=cpu_threads,
                        num_workers=workers,
                    )
                except Exception as fallback_exc:
                    raise TranscriptionError(
                        "Modello Whisper non disponibile.",
                        detail=str(fallback_exc),
                    ) from fallback_exc
                self._models[model_key] = model
                self._models[(model_name, "cpu", "int8", cpu_threads, workers)] = model
                return model
            raise TranscriptionError(
                "Modello Whisper non disponibile.",
                detail=str(exc),
            ) from exc

        self._models[model_key] = model
        return model

    def _progress_message(self, current: float, total: float, started_at: float) -> str:
        elapsed = max(1.0, time.monotonic() - started_at)
        ratio = min(1.0, current / total) if total else 0.0
        remaining = int((elapsed / ratio) - elapsed) if ratio > 0.02 else None
        base = f"Trascritti {self._format_time(current)} di {self._format_time(total)}."
        if remaining is None:
            return base
        return f"{base} Stima residua: {self._format_time(remaining)}."

    def _format_time(self, seconds: float) -> str:
        value = max(0, int(seconds))
        hours, remainder = divmod(value, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes:02d}m"
        return f"{minutes}m {secs:02d}s"
