from __future__ import annotations

import os
import shutil
from pathlib import Path

import imageio_ffmpeg

from crd_notes.core.errors import ConversionError


class FFmpegLocator:
    def locate(self) -> Path:
        configured_path = os.getenv("CRD_NOTES_FFMPEG", "").strip().strip('"')
        if configured_path:
            configured = Path(configured_path).expanduser()
            if configured.is_file():
                return configured

        system_path = shutil.which("ffmpeg")
        if system_path:
            return Path(system_path)

        try:
            bundled = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:  # pragma: no cover - dipende dall'ambiente locale
            raise ConversionError(
                "ffmpeg non e' disponibile e non e' stato possibile scaricarlo automaticamente.",
                detail=str(exc),
            ) from exc

        return Path(bundled)
