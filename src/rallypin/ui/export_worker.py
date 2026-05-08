"""Background worker thread for FFmpeg export jobs."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from rallypin.core.models import VideoSegment
from rallypin.core.video_processing import (
    VideoProcessingError,
    export_segments_concatenated,
    export_segments_individually,
)


class ExportWorker(QThread):
    """Executes export jobs in a worker thread to keep UI responsive."""

    completed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        input_video: Path,
        segments: list[VideoSegment],
        mode: str,
        output_path: Path,
        parent: object | None = None,
    ) -> None:
        """Initialize an export worker with immutable job inputs."""
        super().__init__(parent)
        self._input_video = input_video
        self._segments = list(segments)
        self._mode = mode
        self._output_path = output_path

    def run(self) -> None:
        """Execute export mode and emit completion/error signals."""
        try:
            if self._mode == "concat":
                output_file = export_segments_concatenated(
                    input_video=self._input_video,
                    segments=self._segments,
                    output_file=self._output_path,
                )
                self.completed.emit(f"Concatenated video exported:\n{output_file}")
                return

            if self._mode == "individual":
                outputs = export_segments_individually(
                    input_video=self._input_video,
                    segments=self._segments,
                    output_dir=self._output_path,
                )
                self.completed.emit(
                    f"Exported {len(outputs)} clips to:\n{self._output_path}",
                )
                return

            self.failed.emit(f"Unsupported export mode: {self._mode}")
        except VideoProcessingError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Unexpected export error: {exc}")

