from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from imageio_ffmpeg import count_frames_and_secs

from rallypin.core.models import VideoSegment
from rallypin.core.video_processing import (
    ExportCancelled,
    VideoProcessingError,
    _available_output_path,
    _individual_clip_path,
    _resolve_ffmpeg_executable,
    export_segments_concatenated,
    export_segments_individually,
)


class VideoProcessingTests(unittest.TestCase):
    def test_clip_names_include_safe_tags_and_do_not_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            segment = VideoSegment(0, 100, ("back/court", "winner"))
            requested = _individual_clip_path(output_dir, 1, segment)
            requested.touch()

            self.assertEqual(requested.name, "Play_001_back_court_winner.mp4")
            self.assertEqual(
                _available_output_path(requested).name, "Play_001_back_court_winner_2.mp4"
            )

    def test_pre_cancelled_export_stops_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp4"
            source.touch()

            with self.assertRaises(ExportCancelled):
                export_segments_individually(
                    source,
                    [VideoSegment(0, 100)],
                    root / "clips",
                    cancel_requested=lambda: True,
                )

    def test_real_ffmpeg_export_produces_individual_and_joined_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp4"
            ffmpeg = _resolve_ffmpeg_executable()
            subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=size=160x90:rate=30",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=800:sample_rate=44100",
                    "-t",
                    "1.2",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-y",
                    str(source),
                ],
                check=True,
                capture_output=True,
            )
            segments = [VideoSegment(100, 450), VideoSegment(600, 1_000)]
            progress: list[tuple[int, int, str]] = []

            clips = export_segments_individually(
                source,
                segments,
                root / "clips",
                progress_callback=lambda done, total, message: progress.append(
                    (done, total, message),
                ),
            )
            joined = export_segments_concatenated(source, segments, root / "joined.mp4")

            self.assertEqual(len(clips), 2)
            self.assertTrue(all(path.stat().st_size > 0 for path in clips))
            self.assertGreater(joined.stat().st_size, 0)
            self.assertEqual(progress[-1][:2], (2, 2))
            _frames, first_duration = count_frames_and_secs(str(clips[0]))
            _frames, joined_duration = count_frames_and_secs(str(joined))
            self.assertGreater(first_duration, 0.25)
            self.assertLess(first_duration, 0.55)
            self.assertGreater(joined_duration, 0.60)
            self.assertLess(joined_duration, 1.00)

    def test_failed_join_does_not_replace_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            invalid_source = root / "invalid.mp4"
            invalid_source.write_bytes(b"not a video")
            destination = root / "existing.mp4"
            destination.write_bytes(b"keep me")

            with self.assertRaises(VideoProcessingError):
                export_segments_concatenated(
                    invalid_source,
                    [VideoSegment(0, 100)],
                    destination,
                )

            self.assertEqual(destination.read_bytes(), b"keep me")
            self.assertFalse(any(root.glob(".rallypin-*")))


if __name__ == "__main__":
    unittest.main()
