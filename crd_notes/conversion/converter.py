from __future__ import annotations

import subprocess
import wave
from pathlib import Path

from crd_notes.conversion.ffmpeg import FFmpegLocator
from crd_notes.core.errors import ConversionError


class MediaConverter:
    def __init__(self, ffmpeg_locator: FFmpegLocator) -> None:
        self.ffmpeg_locator = ffmpeg_locator

    def to_wav(self, source: Path, destination: Path) -> tuple[Path, float | None]:
        destination.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg = self.ffmpeg_locator.locate()
        command = [
            str(ffmpeg),
            "-y",
            "-i",
            str(source),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(destination),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise ConversionError(
                "Conversione non avviata: ffmpeg non e' eseguibile.",
                detail=str(exc),
            ) from exc

        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise ConversionError(
                "Conversione audio non riuscita.",
                detail=detail[-2000:] if detail else None,
            )

        return destination, self._read_wav_duration(destination)

    def _read_wav_duration(self, path: Path) -> float | None:
        try:
            with wave.open(str(path), "rb") as audio:
                frames = audio.getnframes()
                rate = audio.getframerate()
                return frames / float(rate) if rate else None
        except wave.Error:
            return None
