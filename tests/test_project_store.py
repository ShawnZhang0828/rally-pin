from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rallypin.core.models import VideoSegment
from rallypin.core.project_store import ProjectFileError, load_project, save_project


class ProjectStoreTests(unittest.TestCase):
    def test_round_trip_uses_relative_video_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "match.mp4"
            video.touch()
            project_path = root / "match.rallypin.json"
            segments = [VideoSegment(100, 900, ("winner",))]

            save_project(project_path, video, segments)
            decoded = json.loads(project_path.read_text(encoding="utf-8"))
            loaded = load_project(project_path)

            self.assertEqual(decoded["video_path"], "match.mp4")
            self.assertEqual(loaded.video_path, video.resolve())
            self.assertEqual(list(loaded.segments), segments)

    def test_nested_relative_path_uses_portable_separators(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_dir = root / "media" / "day-one"
            video_dir.mkdir(parents=True)
            video = video_dir / "match.mp4"
            video.touch()
            project_path = root / "projects" / "match.rallypin.json"

            save_project(project_path, video, [])
            decoded = json.loads(project_path.read_text(encoding="utf-8"))

            self.assertNotIn("\\", decoded["video_path"])
            self.assertEqual(load_project(project_path).video_path, video.resolve())

    def test_invalid_json_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "broken.rallypin.json"
            project_path.write_text("{broken", encoding="utf-8")

            with self.assertRaises(ProjectFileError):
                load_project(project_path)

    def test_invalid_segment_is_reported_with_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "broken.rallypin.json"
            project_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "video_path": "match.mp4",
                        "segments": [{"start_ms": 100, "end_ms": 50, "tags": []}],
                    },
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectFileError, "Invalid segment 1"):
                load_project(project_path)


if __name__ == "__main__":
    unittest.main()
