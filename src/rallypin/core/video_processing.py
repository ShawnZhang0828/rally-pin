"""FFmpeg-powered clipping and export helpers."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from functools import lru_cache
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe

from rallypin.core.models import VideoSegment
from rallypin.core.tag_utils import sanitize_tag_for_filename

ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


class VideoProcessingError(RuntimeError):
    """Raised when FFmpeg processing fails."""


class ExportCancelled(VideoProcessingError):
    """Raised when the user cancels an active export."""


def export_segments_individually(
    input_video: Path,
    segments: list[VideoSegment],
    output_dir: Path,
    progress_callback: ProgressCallback | None = None,
    cancel_requested: CancelCheck | None = None,
) -> list[Path]:
    """Export each segment as an accurate, independently playable MP4 file."""
    _validate_input(input_video, segments)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise VideoProcessingError(f"Could not create the export folder: {exc}") from exc

    outputs: list[Path] = []
    total = len(segments)
    for index, segment in enumerate(segments, start=1):
        _raise_if_cancelled(cancel_requested)
        output_path = _available_output_path(_individual_clip_path(output_dir, index, segment))
        temporary_output = output_dir / f".rallypin-{uuid.uuid4().hex}.mp4"
        try:
            _run_ffmpeg_extract(
                input_video,
                temporary_output,
                segment,
                cancel_requested=cancel_requested,
            )
            try:
                os.replace(temporary_output, output_path)
            except OSError as exc:
                raise VideoProcessingError(f"Could not finish clip {index}: {exc}") from exc
        finally:
            temporary_output.unlink(missing_ok=True)
        outputs.append(output_path)
        _report_progress(progress_callback, index, total, f"Exported clip {index} of {total}")
    return outputs


def export_segments_concatenated(
    input_video: Path,
    segments: list[VideoSegment],
    output_file: Path,
    progress_callback: ProgressCallback | None = None,
    cancel_requested: CancelCheck | None = None,
) -> Path:
    """Accurately extract and concatenate segments into one MP4 file."""
    _validate_input(input_video, segments)
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise VideoProcessingError(f"Could not create the export folder: {exc}") from exc

    total_steps = len(segments) + 1
    try:
        with tempfile.TemporaryDirectory(prefix=".rallypin-", dir=output_file.parent) as temp_dir:
            temp_path = Path(temp_dir)
            segment_files: list[Path] = []
            for index, segment in enumerate(segments, start=1):
                _raise_if_cancelled(cancel_requested)
                clip_path = temp_path / f"clip_{index:04d}.mp4"
                _run_ffmpeg_extract(
                    input_video,
                    clip_path,
                    segment,
                    cancel_requested=cancel_requested,
                )
                segment_files.append(clip_path)
                _report_progress(
                    progress_callback,
                    index,
                    total_steps,
                    f"Prepared rally {index} of {len(segments)}",
                )

            _raise_if_cancelled(cancel_requested)
            concat_list = temp_path / "concat_list.txt"
            staged_output = temp_path / "finished.mp4"
            _write_concat_list_file(concat_list, segment_files)
            _run_ffmpeg_concat(concat_list, staged_output, cancel_requested=cancel_requested)
            _raise_if_cancelled(cancel_requested)
            os.replace(staged_output, output_file)
    except ExportCancelled:
        raise
    except VideoProcessingError:
        raise
    except OSError as exc:
        raise VideoProcessingError(f"Could not write the final export: {exc}") from exc

    _report_progress(progress_callback, total_steps, total_steps, "Export complete")
    return output_file


def _individual_clip_path(output_dir: Path, index: int, segment: VideoSegment) -> Path:
    """Build an output filename that includes sanitized tags when present."""
    base = f"Play_{index:03d}"
    if segment.tags:
        parts = "_".join(sanitize_tag_for_filename(tag) for tag in segment.tags)
        base = f"{base}_{parts[:120].rstrip('_')}"
    return output_dir / f"{base}.mp4"


def _available_output_path(requested_path: Path) -> Path:
    """Avoid silently overwriting an existing individual clip."""
    if not requested_path.exists():
        return requested_path
    counter = 2
    while True:
        candidate = requested_path.with_name(
            f"{requested_path.stem}_{counter}{requested_path.suffix}"
        )
        if not candidate.exists():
            return candidate
        counter += 1


def _validate_input(input_video: Path, segments: list[VideoSegment]) -> None:
    """Validate required export inputs."""
    if not input_video.exists() or not input_video.is_file():
        raise VideoProcessingError(f"Input video not found: {input_video}")
    if not segments:
        raise VideoProcessingError("No segments available for export.")


def _run_ffmpeg_extract(
    input_video: Path,
    output_file: Path,
    segment: VideoSegment,
    cancel_requested: CancelCheck | None = None,
) -> None:
    """Accurately seek, decode, and encode one segment for clean boundaries."""
    start_seconds = segment.start_ms / 1000.0
    duration_seconds = segment.duration_ms / 1000.0
    command = [
        _resolve_ffmpeg_executable(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-ss",
        f"{start_seconds:.3f}",
        "-i",
        str(input_video),
        "-t",
        f"{duration_seconds:.3f}",
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-map_metadata",
        "-1",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-y",
        str(output_file),
    ]
    _run_process(command, "Failed to extract a rally", cancel_requested)


def _run_ffmpeg_concat(
    concat_list: Path,
    output_file: Path,
    cancel_requested: CancelCheck | None = None,
) -> None:
    """Concatenate consistently encoded clips without another video encode."""
    command = [
        _resolve_ffmpeg_executable(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        "-y",
        str(output_file),
    ]
    _run_process(command, "Failed to join rallies", cancel_requested)


def _run_process(
    command: list[str],
    error_prefix: str,
    cancel_requested: CancelCheck | None,
) -> None:
    """Run FFmpeg without a console window and terminate it on cancellation."""
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creation_flags,
        )
    except OSError as exc:
        raise VideoProcessingError(f"{error_prefix}: {exc}") from exc

    while True:
        try:
            _stdout, stderr = process.communicate(timeout=0.15)
            break
        except subprocess.TimeoutExpired:
            if cancel_requested is not None and cancel_requested():
                with suppress(OSError):
                    process.terminate()
                try:
                    process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                raise ExportCancelled("Export cancelled.") from None
            time.sleep(0.02)

    if process.returncode != 0:
        details = stderr.decode("utf-8", errors="replace").strip()
        if len(details) > 2000:
            details = details[-2000:]
        suffix = f": {details}" if details else "."
        raise VideoProcessingError(f"{error_prefix}{suffix}")


def _write_concat_list_file(list_path: Path, segment_paths: list[Path]) -> None:
    """Write a concat demuxer list for generated, quote-free temporary paths."""
    lines = [f"file '{segment_path.as_posix()}'" for segment_path in segment_paths]
    list_path.write_text("\n".join(lines), encoding="utf-8")


@lru_cache(maxsize=1)
def _resolve_ffmpeg_executable() -> str:
    """Resolve FFmpeg from PATH or the imageio-ffmpeg bundled binary."""
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


def _report_progress(
    callback: ProgressCallback | None,
    completed: int,
    total: int,
    message: str,
) -> None:
    """Send a progress update when the caller supplied a callback."""
    if callback is not None:
        callback(completed, total, message)


def _raise_if_cancelled(cancel_requested: CancelCheck | None) -> None:
    """Stop between FFmpeg jobs when cancellation has been requested."""
    if cancel_requested is not None and cancel_requested():
        raise ExportCancelled("Export cancelled.")


def _ffmpeg_not_found_message() -> str:
    """Return actionable FFmpeg installation guidance."""
    return (
        "FFmpeg executable not found. Reinstall RallyPin or install FFmpeg on your system, "
        "then restart the app."
    )
