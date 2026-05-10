from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from crd_notes.conversion.ffmpeg import FFmpegLocator


class FFmpegLocatorTests(unittest.TestCase):
    def test_prefers_explicit_crd_notes_ffmpeg_path(self) -> None:
        expected = Path("C:/tools/ffmpeg/bin/ffmpeg.exe")

        with patch.dict("os.environ", {"CRD_NOTES_FFMPEG": str(expected)}, clear=False):
            with patch("crd_notes.conversion.ffmpeg.Path.is_file", return_value=True):
                with patch("crd_notes.conversion.ffmpeg.shutil.which", return_value=None):
                    locator = FFmpegLocator()

                    self.assertEqual(locator.locate(), expected)

    def test_falls_back_to_system_ffmpeg_when_custom_path_is_invalid(self) -> None:
        with patch.dict("os.environ", {"CRD_NOTES_FFMPEG": "C:/missing/ffmpeg.exe"}, clear=False):
            with patch("crd_notes.conversion.ffmpeg.Path.is_file", return_value=False):
                with patch("crd_notes.conversion.ffmpeg.shutil.which", return_value="C:/bin/ffmpeg.exe"):
                    locator = FFmpegLocator()

                    self.assertEqual(locator.locate(), Path("C:/bin/ffmpeg.exe"))


if __name__ == "__main__":
    unittest.main()
