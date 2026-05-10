from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from crd_notes.recording.service import RecordingService, RecordingSession


class FakeFFmpegLocator:
    def locate(self) -> Path:
        return Path("ffmpeg")


class RecordingServiceTests(unittest.TestCase):
    def service(self) -> RecordingService:
        return RecordingService(
            ffmpeg_locator=FakeFFmpegLocator(),
            job_runner=object(),  # type: ignore[arg-type]
        )

    def test_dshow_system_sources_do_not_treat_generic_virtual_microphones_as_windows_audio(
        self,
    ) -> None:
        service = self.service()

        with patch.object(service, "_supports_wasapi_loopback", return_value=False):
            sources = service._system_audio_sources(
                [
                    "Microphone (4- Shure MV7)",
                    "Headset Microphone (Oculus Virtual Audio Device)",
                    "CABLE Output (VB-Audio Virtual Cable)",
                    "Stereo Mix (Realtek(R) Audio)",
                ]
            )

        self.assertEqual(
            sources,
            [
                {
                    "id": "dshow:CABLE Output (VB-Audio Virtual Cable)",
                    "label": "CABLE Output (VB-Audio Virtual Cable)",
                },
                {
                    "id": "dshow:Stereo Mix (Realtek(R) Audio)",
                    "label": "Stereo Mix (Realtek(R) Audio)",
                },
            ],
        )

    def test_wasapi_support_requires_loopback_option(self) -> None:
        service = self.service()

        with patch("crd_notes.recording.service.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "Demuxer wasapi [Windows audio session API input device]:\n"
            run.return_value.stderr = ""

            self.assertFalse(service._supports_wasapi_loopback())

        with patch("crd_notes.recording.service.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = (
                "wasapi indev AVOptions:\n  -loopback <boolean> capture render endpoint\n"
            )
            run.return_value.stderr = ""

            self.assertTrue(service._supports_wasapi_loopback())

    def test_microphone_system_command_uses_legacy_compatible_amix_options(self) -> None:
        service = self.service()
        session = RecordingSession(
            id="recording-id",
            workspace_id="default",
            title="Recording",
            recorded_on=None,
            notes="",
            participants=[],
            mode="microphone_system",
            microphone_device="Microphone",
            system_device="dshow:CABLE Output (VB-Audio Virtual Cable)",
            window_hint="",
        )

        command = service._recording_command(session, Path("out.wav"))

        self.assertIn("amix=inputs=2:duration=longest", command)
        self.assertNotIn("normalize=0", command)


if __name__ == "__main__":
    unittest.main()
