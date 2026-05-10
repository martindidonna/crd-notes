from __future__ import annotations

import re
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from threading import Lock
from time import monotonic, sleep
from typing import Literal

from crd_notes.conversion.ffmpeg import FFmpegLocator
from crd_notes.core.errors import CrdNotesError
from crd_notes.core.paths import RECORDINGS_DIR
from crd_notes.jobs import JobRunner
from crd_notes.library.models import DEFAULT_WORKSPACE_ID

RecordingMode = Literal["microphone", "system", "microphone_system", "window"]


@dataclass
class RecordingBookmark:
    id: str
    label: str
    timestamp_seconds: float
    created_at: datetime


@dataclass
class RecordingSession:
    id: str
    workspace_id: str
    title: str
    recorded_on: date | None
    notes: str
    participants: list[str]
    mode: RecordingMode
    microphone_device: str
    system_device: str
    window_hint: str
    status: str = "recording"
    accumulated_seconds: float = 0
    segment_started_at: float | None = None
    segment_index: int = 0
    segments: list[Path] = field(default_factory=list)
    bookmarks: list[RecordingBookmark] = field(default_factory=list)
    process: subprocess.Popen[str] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str = ""


class RecordingService:
    def __init__(self, *, ffmpeg_locator: FFmpegLocator, job_runner: JobRunner) -> None:
        self.ffmpeg_locator = ffmpeg_locator
        self.job_runner = job_runner
        self._sessions: dict[str, RecordingSession] = {}
        self._lock = Lock()

    def list_sources(self) -> dict[str, object]:
        devices = self._list_dshow_audio_devices()
        system_devices = self._system_audio_sources(devices)
        window_detail = (
            "La cattura isolata di una singola finestra non e' disponibile con ffmpeg "
            "standard. Seleziona un device virtuale dedicato oppure registra il mix di sistema."
        )
        if not system_devices:
            window_detail = (
                "Audio Windows non disponibile con il ffmpeg incluso. Installa un ffmpeg con "
                "WASAPI loopback oppure abilita un device tipo Stereo Mix/virtual audio cable."
            )
        return {
            "microphones": [{"id": item, "label": item} for item in devices],
            "system": system_devices,
            "window_supported": False,
            "window_detail": window_detail,
        }

    def start(
        self,
        *,
        workspace_id: str,
        title: str,
        recorded_on: date | None,
        notes: str,
        participants: list[str],
        mode: RecordingMode,
        microphone_device: str = "",
        system_device: str = "wasapi:default",
        window_hint: str = "",
    ) -> RecordingSession:
        if mode == "window":
            raise CrdNotesError(
                "Registrazione finestra non disponibile.",
                detail=(
                    "Il backend attuale puo' registrare microfono e audio Windows. "
                    "Per isolare una singola finestra serve un driver virtuale o un backend "
                    "Windows Audio Session dedicato."
                ),
            )

        session = RecordingSession(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id or DEFAULT_WORKSPACE_ID,
            title=title.strip() or "Registrazione",
            recorded_on=recorded_on,
            notes=notes,
            participants=participants,
            mode=mode,
            microphone_device=microphone_device,
            system_device=system_device,
            window_hint=window_hint,
        )
        with self._lock:
            self._sessions[session.id] = session
        try:
            self._start_segment(session)
        except Exception:
            with self._lock:
                self._sessions.pop(session.id, None)
            raise
        return self.read(session.id)

    def read(self, session_id: str) -> RecordingSession:
        with self._lock:
            session = self._get(session_id)
            session.updated_at = datetime.now(timezone.utc)
            return session

    def elapsed_seconds(self, session: RecordingSession) -> float:
        return self._elapsed_seconds(session)

    def pause(self, session_id: str) -> RecordingSession:
        with self._lock:
            session = self._get(session_id)
            if session.status != "recording":
                return session
        self._stop_current_segment(session)
        with self._lock:
            session.status = "paused"
            session.updated_at = datetime.now(timezone.utc)
        return self.read(session_id)

    def resume(self, session_id: str) -> RecordingSession:
        with self._lock:
            session = self._get(session_id)
            if session.status != "paused":
                return session
            session.status = "recording"
        self._start_segment(session)
        return self.read(session_id)

    def add_bookmark(self, session_id: str, label: str) -> RecordingSession:
        with self._lock:
            session = self._get(session_id)
            bookmark = RecordingBookmark(
                id=str(uuid.uuid4()),
                label=label.strip() or f"Segnalibro {len(session.bookmarks) + 1}",
                timestamp_seconds=self._elapsed_seconds(session),
                created_at=datetime.now(timezone.utc),
            )
            session.bookmarks.append(bookmark)
            session.updated_at = bookmark.created_at
        return self.read(session_id)

    def stop(self, session_id: str, *, summarize: bool, prompt_id: str, provider: str | None) -> str:
        with self._lock:
            session = self._get(session_id)
        if session.status == "recording":
            self._stop_current_segment(session)

        with self._lock:
            session.status = "finalizing"
            session.updated_at = datetime.now(timezone.utc)

        final_path = self._finalize(session)
        notes = self._notes_with_bookmarks(session)
        payload = {
            "source_path": str(final_path),
            "source_filename": final_path.name,
            "workspace_id": session.workspace_id,
            "title": session.title,
            "recorded_on": session.recorded_on.isoformat() if session.recorded_on else None,
            "notes": notes,
            "participants": session.participants,
            "summarize": summarize,
            "prompt_id": prompt_id,
            "provider": provider,
        }
        job = self.job_runner.create_job(payload)

        with self._lock:
            session.status = "completed"
            session.updated_at = datetime.now(timezone.utc)
        return job.id

    def cancel(self, session_id: str) -> None:
        with self._lock:
            session = self._get(session_id)
        if session.status == "recording":
            self._stop_current_segment(session)
        for segment in session.segments:
            segment.unlink(missing_ok=True)
        with self._lock:
            self._sessions.pop(session_id, None)

    def _get(self, session_id: str) -> RecordingSession:
        session = self._sessions.get(session_id)
        if not session:
            raise CrdNotesError("Registrazione non trovata.")
        return session

    def _start_segment(self, session: RecordingSession) -> None:
        session_dir = RECORDINGS_DIR / session.id
        session_dir.mkdir(parents=True, exist_ok=True)
        segment = session_dir / f"segment-{session.segment_index:03d}.wav"
        session.segment_index += 1
        command = self._recording_command(session, segment)
        try:
            log_handle = segment.with_suffix(".log").open("w", encoding="utf-8")
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=log_handle,
                stderr=log_handle,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise CrdNotesError("Registrazione non avviata.", detail=str(exc)) from exc
        finally:
            if "log_handle" in locals():
                log_handle.close()

        sleep(0.35)
        if process.poll() is not None:
            detail = segment.with_suffix(".log").read_text(encoding="utf-8", errors="replace")[-2000:]
            raise CrdNotesError("Registrazione non avviata.", detail=detail or None)

        with self._lock:
            session.process = process
            session.segment_started_at = monotonic()
            session.segments.append(segment)
            session.status = "recording"
            session.updated_at = datetime.now(timezone.utc)

    def _stop_current_segment(self, session: RecordingSession) -> None:
        process = session.process
        if process and process.poll() is None:
            try:
                if process.stdin:
                    process.stdin.write("q\n")
                    process.stdin.flush()
                process.wait(timeout=6)
            except Exception:
                process.terminate()
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill()
        if session.segment_started_at is not None:
            session.accumulated_seconds += max(0, monotonic() - session.segment_started_at)
        session.segment_started_at = None
        session.process = None

    def _finalize(self, session: RecordingSession) -> Path:
        existing_segments = [path for path in session.segments if path.exists() and path.stat().st_size > 0]
        if not existing_segments:
            raise CrdNotesError("Registrazione vuota.", detail="Nessun segmento audio e' stato salvato.")

        final_path = RECORDINGS_DIR / f"{session.id}.wav"
        if len(existing_segments) == 1:
            existing_segments[0].replace(final_path)
            return final_path

        concat_file = RECORDINGS_DIR / session.id / "segments.txt"
        concat_file.write_text(
            "\n".join(f"file '{path.as_posix()}'" for path in existing_segments),
            encoding="utf-8",
        )
        command = [
            str(self.ffmpeg_locator.locate()),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(final_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise CrdNotesError(
                "Finalizzazione registrazione non riuscita.",
                detail=(result.stderr or result.stdout)[-2000:],
            )
        return final_path

    def _recording_command(self, session: RecordingSession, destination: Path) -> list[str]:
        ffmpeg = str(self.ffmpeg_locator.locate())
        base = [ffmpeg, "-y", "-hide_banner"]
        mic = session.microphone_device
        system = session.system_device

        if session.mode == "microphone":
            if not mic:
                raise CrdNotesError(
                    "Microfono non selezionato.",
                    detail="Apri il menu sorgente e scegli un dispositivo audio di ingresso.",
                )
            return [
                *base,
                "-f",
                "dshow",
                "-i",
                f"audio={mic}",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(destination),
            ]

        if session.mode == "system":
            system_input = self._system_input_args(system)
            return [
                *base,
                *system_input,
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(destination),
            ]

        if not mic:
            raise CrdNotesError(
                "Microfono non selezionato.",
                detail="Per registrare microfono e Windows serve anche il dispositivo microfono.",
            )
        system_input = self._system_input_args(system)
        return [
            *base,
            "-f",
            "dshow",
            "-i",
            f"audio={mic}",
            *system_input,
            "-filter_complex",
            "amix=inputs=2:duration=longest",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(destination),
        ]

    def _elapsed_seconds(self, session: RecordingSession) -> float:
        active = 0.0
        if session.status == "recording" and session.segment_started_at is not None:
            active = max(0, monotonic() - session.segment_started_at)
        return round(session.accumulated_seconds + active, 2)

    def _notes_with_bookmarks(self, session: RecordingSession) -> str:
        lines = [session.notes.strip()] if session.notes.strip() else []
        if session.bookmarks:
            lines.append("Segnalibri registrazione:")
            for bookmark in session.bookmarks:
                lines.append(f"- {self._format_timestamp(bookmark.timestamp_seconds)} {bookmark.label}")
        return "\n".join(lines)

    def _list_dshow_audio_devices(self) -> list[str]:
        command = [str(self.ffmpeg_locator.locate()), "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
            )
        except Exception:
            return []
        output = "\n".join([result.stderr or "", result.stdout or ""])
        devices: list[str] = []
        in_audio_section = False
        for line in output.splitlines():
            if "DirectShow audio devices" in line:
                in_audio_section = True
                continue
            if "DirectShow video devices" in line:
                in_audio_section = False
            if not in_audio_section or "Alternative name" in line:
                continue
            match = re.search(r'"([^"]+)"', line)
            if match:
                devices.append(match.group(1))
        return devices

    def _system_audio_sources(self, dshow_devices: list[str]) -> list[dict[str, str]]:
        sources: list[dict[str, str]] = []
        if self._supports_wasapi_loopback():
            sources.append(
                {
                    "id": "wasapi:default",
                    "label": "Audio Windows predefinito (WASAPI loopback)",
                }
            )

        for device in dshow_devices:
            if self._is_dshow_system_audio_device(device):
                sources.append({"id": f"dshow:{device}", "label": device})
        return sources

    def _is_dshow_system_audio_device(self, device: str) -> bool:
        normalized = device.lower()
        exact_markers = ("stereo mix", "mix stereo", "what u hear")
        if any(marker in normalized for marker in exact_markers):
            return True

        virtual_loopback_markers = (
            "cable output",
            "vb-audio",
            "voicemeeter output",
            "voicemeeter aux output",
            "blackhole",
            "soundflower",
        )
        return any(marker in normalized for marker in virtual_loopback_markers)

    def _supports_wasapi_loopback(self) -> bool:
        try:
            result = subprocess.run(
                [str(self.ffmpeg_locator.locate()), "-hide_banner", "-h", "demuxer=wasapi"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
            )
        except Exception:
            return False
        output = f"{result.stdout}\n{result.stderr}".lower()
        return result.returncode == 0 and re.search(r"(?m)^\s*-loopback\b", output) is not None

    def _system_input_args(self, system_device: str) -> list[str]:
        if system_device.startswith("dshow:"):
            device = system_device.removeprefix("dshow:")
            return ["-f", "dshow", "-i", f"audio={device}"]
        if system_device.startswith("wasapi:") and self._supports_wasapi_loopback():
            device = system_device.removeprefix("wasapi:") or "default"
            return ["-f", "wasapi", "-loopback", "1", "-i", device]
        raise CrdNotesError(
            "Audio Windows non disponibile.",
            detail=(
                "Il ffmpeg configurato non espone WASAPI loopback e non e' stato trovato "
                "un device DirectShow tipo Stereo Mix o virtual audio cable."
            ),
        )

    def _format_timestamp(self, seconds: float) -> str:
        total = int(seconds)
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
