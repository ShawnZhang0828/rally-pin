"""FFmpeg-powered batch clipping and export helpers."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import ffmpeg
from imageio_ffmpeg import get_ffmpeg_exe

from rallypin.core.models import VideoSegment


class VideoProcessingError(RuntimeError):
    """Raised when FFmpeg processing fails."""


def export_segments_individually(
    input_video: Path,
    segments: list[VideoSegment],
    output_dir: Path,
) -> list[Path]:
    """Export each segment to an independent file via stream copy."""
    _validate_input(input_video, segments)
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    for index, segment in enumerate(segments, start=1):
        output_path = output_dir / f"Play_{index:03d}.mp4"
        _run_ffmpeg_extract(input_video, output_path, segment)
        outputs.append(output_path)
    return outputs


def export_segments_concatenated(
    input_video: Path,
    segments: list[VideoSegment],
    output_file: Path,
) -> Path:
    """Extract then concatenate segments into a single output file."""
    _validate_input(input_video, segments)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="rallypin_") as temp_dir:
        temp_path = Path(temp_dir)
        segment_files: list[Path] = []
        for index, segment in enumerate(segments, start=1):
            clip_path = temp_path / f"clip_{index:03d}.mp4"
            _run_ffmpeg_extract(input_video, clip_path, segment)
            segment_files.append(clip_path)

        concat_list = temp_path / "concat_list.txt"
        _write_concat_list_file(concat_list, segment_files)
        _run_ffmpeg_concat(concat_list, output_file)

    return output_file


def _validate_input(input_video: Path, segments: list[VideoSegment]) -> None:
    """Validate required export inputs."""
    if not input_video.exists():
        raise VideoProcessingError(f"Input video not found: {input_video}")
    if not segments:
        raise VideoProcessingError("No segments available for export.")


def _run_ffmpeg_extract(input_video: Path, output_file: Path, segment: VideoSegment) -> None:
    """Run FFmpeg trim command using stream copy for speed."""
    start_seconds = segment.start_ms / 1000.0
    end_seconds = segment.end_ms / 1000.0
    ffmpeg_executable = _resolve_ffmpeg_executable()

    try:
        (
            ffmpeg.input(str(input_video), ss=start_seconds, to=end_seconds)
            .output(str(output_file), c="copy", loglevel="error", y=None)
            .run(cmd=ffmpeg_executable, capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        raise VideoProcessingError(f"Failed to extract segment: {stderr}") from exc
    except FileNotFoundError as exc:
        raise VideoProcessingError(_ffmpeg_not_found_message()) from exc


def _run_ffmpeg_concat(concat_list: Path, output_file: Path) -> None:
    """Run FFmpeg concat demuxer in copy mode."""
    ffmpeg_executable = _resolve_ffmpeg_executable()
    try:
        (
            ffmpeg.input(str(concat_list), format="concat", safe=0)
            .output(str(output_file), c="copy", loglevel="error", y=None)
            .run(cmd=ffmpeg_executable, capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        raise VideoProcessingError(f"Failed to concatenate segments: {stderr}") from exc
    except FileNotFoundError as exc:
        raise VideoProcessingError(_ffmpeg_not_found_message()) from exc


def _write_concat_list_file(list_path: Path, segment_paths: list[Path]) -> None:
    """Write concat demuxer list file referencing extracted clips."""
    lines = [f"file '{segment_path.as_posix()}'" for segment_path in segment_paths]
    list_path.write_text("\n".join(lines), encoding="utf-8")


def _resolve_ffmpeg_executable() -> str:
    """Resolve FFmpeg executable path from PATH or bundled binary."""
    ffmpeg_on_path = shutil.which("ffmpeg")
    if ffmpeg_on_path:
        return ffmpeg_on_path

    try:
        bundled = get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001
        raise VideoProcessingError(_ffmpeg_not_found_message()) from exc

    if not bundled or not Path(bundled).exists():
        raise VideoProcessingError(_ffmpeg_not_found_message())
    return bundled


def _ffmpeg_not_found_message() -> str:
    """Return actionable FFmpeg installation guidance."""
    return (
        "FFmpeg executable not found. Install FFmpeg or run `pip install imageio-ffmpeg`, "
        "then restart RallyPin."
    )

