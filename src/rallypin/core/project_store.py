"""Read and write RallyPin project files."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rallypin.core.models import VideoSegment
from rallypin.core.tag_utils import parse_tags

PROJECT_VERSION = 1


class ProjectFileError(RuntimeError):
    """Raised when a RallyPin project cannot be read or written safely."""


@dataclass(frozen=True, slots=True)
class RallyProject:
    """A video source and its ordered rally segments."""

    video_path: Path
    segments: tuple[VideoSegment, ...]


def save_project(
    project_path: Path,
    video_path: Path,
    segments: list[VideoSegment],
) -> Path:
    """Atomically save a project, using a relative video path when possible."""
    project_path = project_path.resolve()
    video_path = video_path.resolve()

    try:
        stored_video_path = Path(os.path.relpath(video_path, project_path.parent)).as_posix()
    except ValueError:
        stored_video_path = str(video_path)

    payload = {
        "version": PROJECT_VERSION,
        "video_path": stored_video_path,
        "segments": [
            {
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
                "tags": list(segment.tags),
            }
            for segment in segments
        ],
    }

    temp_name: str | None = None
    try:
        project_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=project_path.parent,
            prefix=f".{project_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_name = temp_file.name
            json.dump(payload, temp_file, indent=2, ensure_ascii=False)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_name, project_path)
    except OSError as exc:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)
        raise ProjectFileError(f"Could not save project: {exc}") from exc

    return project_path


def load_project(project_path: Path) -> RallyProject:
    """Load and validate a RallyPin project file."""
    project_path = project_path.resolve()
    try:
        payload = json.loads(project_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProjectFileError(f"Could not read project: {exc}") from exc

    if not isinstance(payload, dict):
        raise ProjectFileError("Project data must be a JSON object.")
    if payload.get("version") != PROJECT_VERSION:
        raise ProjectFileError(
            f"Unsupported project version: {payload.get('version')!r}. "
            f"This build supports version {PROJECT_VERSION}.",
        )

    raw_video_path = payload.get("video_path")
    if not isinstance(raw_video_path, str) or not raw_video_path.strip():
        raise ProjectFileError("Project video_path must be a non-empty string.")
    video_path = Path(raw_video_path)
    if not video_path.is_absolute():
        video_path = project_path.parent / video_path
    video_path = video_path.resolve()

    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list):
        raise ProjectFileError("Project segments must be a list.")

    segments: list[VideoSegment] = []
    for index, raw_segment in enumerate(raw_segments, start=1):
        try:
            segments.append(_parse_segment(raw_segment))
        except (TypeError, ValueError) as exc:
            raise ProjectFileError(f"Invalid segment {index}: {exc}") from exc

    return RallyProject(video_path=video_path, segments=tuple(segments))


def _parse_segment(raw_segment: Any) -> VideoSegment:
    """Convert one decoded segment object to a validated model."""
    if not isinstance(raw_segment, dict):
        raise TypeError("segment data must be an object.")

    start_ms = raw_segment.get("start_ms")
    end_ms = raw_segment.get("end_ms")
    if isinstance(start_ms, bool) or not isinstance(start_ms, int):
        raise TypeError("start_ms must be an integer.")
    if isinstance(end_ms, bool) or not isinstance(end_ms, int):
        raise TypeError("end_ms must be an integer.")

    raw_tags = raw_segment.get("tags", [])
    if not isinstance(raw_tags, list) or not all(isinstance(tag, str) for tag in raw_tags):
        raise TypeError("tags must be a list of strings.")
    tags = parse_tags(",".join(raw_tags))
    return VideoSegment(start_ms=start_ms, end_ms=end_ms, tags=tags)
