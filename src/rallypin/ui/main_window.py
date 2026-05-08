"""Main application window for RallyPin."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rallypin.core.models import VideoSegment
from rallypin.core.segment_manager import SegmentManager
from rallypin.core.time_utils import format_milliseconds, parse_timestamp_to_milliseconds
from rallypin.core.video_player_controller import VideoPlayerController
from rallypin.ui.export_worker import ExportWorker


class MainWindow(QMainWindow):
    """Main RallyPin window containing the video review player."""

    PLAYBACK_SPEEDS: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)

    def __init__(self) -> None:
        """Initialize widgets, layout, and event bindings."""
        super().__init__()
        self.setWindowTitle("RallyPin - Badminton Video Clipping Tool")
        self.resize(1280, 760)

        self._controller = VideoPlayerController(self)
        self._segment_manager = SegmentManager()
        self._is_user_seeking: bool = False
        self._video_path: Path | None = None
        self._export_worker: ExportWorker | None = None

        self._video_widget = QVideoWidget(self)
        self._video_widget.setMinimumHeight(540)
        self._controller.media_player.setVideoOutput(self._video_widget)

        self._open_button = QPushButton("Open Video", self)
        self._play_pause_button = QPushButton("Play", self)
        self._play_pause_button.setEnabled(False)

        self._position_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._position_slider.setRange(0, 0)
        self._position_slider.setEnabled(False)

        self._position_label = QLabel("00:00:00.000 / 00:00:00.000", self)
        self._position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._speed_label = QLabel("Speed:", self)
        self._speed_combo = QComboBox(self)
        for speed in self.PLAYBACK_SPEEDS:
            self._speed_combo.addItem(f"{speed:.2f}x", speed)
        self._speed_combo.setCurrentText("1.00x")
        self._speed_combo.setEnabled(False)

        self._pin_start_button = QPushButton("Pin Start (I)", self)
        self._pin_end_button = QPushButton("Pin End (O)", self)
        self._delete_segment_button = QPushButton("Delete Selected", self)
        self._clear_segments_button = QPushButton("Clear Segments", self)
        self._export_concat_button = QPushButton("Export Concatenated", self)
        self._export_individual_button = QPushButton("Export Individual Clips", self)

        self._segments_table = QTableWidget(self)
        self._segments_table.setColumnCount(4)
        self._segments_table.setHorizontalHeaderLabels(("Play", "Start", "End", "Duration"))
        header = self._segments_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._segments_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._segments_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self._pending_start_label = QLabel("Pending Start: None", self)
        self._status_label = QLabel("Load a video to begin tagging rallies.", self)

        self._shortcut_pin_start = QShortcut(QKeySequence("I"), self)
        self._shortcut_pin_end = QShortcut(QKeySequence("O"), self)

        self._build_layout()
        self._bind_events()
        self._refresh_ui_state()

    def _build_layout(self) -> None:
        """Compose the top-level layout hierarchy."""
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self._open_button)
        controls_layout.addWidget(self._play_pause_button)
        controls_layout.addWidget(self._speed_label)
        controls_layout.addWidget(self._speed_combo)
        controls_layout.addStretch(1)

        tagging_layout = QHBoxLayout()
        tagging_layout.addWidget(self._pin_start_button)
        tagging_layout.addWidget(self._pin_end_button)
        tagging_layout.addWidget(self._delete_segment_button)
        tagging_layout.addWidget(self._clear_segments_button)

        export_layout = QHBoxLayout()
        export_layout.addWidget(self._export_concat_button)
        export_layout.addWidget(self._export_individual_button)
        export_layout.addStretch(1)

        root_layout = QVBoxLayout()
        root_layout.addWidget(self._video_widget)
        root_layout.addWidget(self._position_slider)
        root_layout.addWidget(self._position_label)
        root_layout.addLayout(controls_layout)
        root_layout.addWidget(self._pending_start_label)
        root_layout.addWidget(self._segments_table)
        root_layout.addLayout(tagging_layout)
        root_layout.addLayout(export_layout)
        root_layout.addWidget(self._status_label)

        container = QWidget(self)
        container.setLayout(root_layout)
        self.setCentralWidget(container)

    def _bind_events(self) -> None:
        """Attach controller and widget signal handlers."""
        self._open_button.clicked.connect(self._open_video)
        self._play_pause_button.clicked.connect(self._controller.toggle_play_pause)

        self._controller.position_changed.connect(self._on_position_changed)
        self._controller.duration_changed.connect(self._on_duration_changed)
        self._controller.playback_state_changed.connect(self._on_playback_state_changed)
        self._controller.media_loaded_changed.connect(self._on_media_loaded_changed)
        self._controller.error_occurred.connect(self._show_error)

        self._position_slider.sliderPressed.connect(self._on_slider_pressed)
        self._position_slider.sliderReleased.connect(self._on_slider_released)
        self._position_slider.valueChanged.connect(self._on_slider_value_changed)
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)

        self._pin_start_button.clicked.connect(self._pin_start)
        self._pin_end_button.clicked.connect(self._pin_end)
        self._delete_segment_button.clicked.connect(self._delete_selected_segments)
        self._clear_segments_button.clicked.connect(self._clear_segments)
        self._export_concat_button.clicked.connect(self._start_export_concat)
        self._export_individual_button.clicked.connect(self._start_export_individual)
        self._segments_table.cellDoubleClicked.connect(self._edit_segment_row)

        self._shortcut_pin_start.activated.connect(self._pin_start)
        self._shortcut_pin_end.activated.connect(self._pin_end)

    def _open_video(self) -> None:
        """Prompt user to select and load an `.mp4` file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            "",
            "Video Files (*.mp4 *.mov *.mkv *.avi)",
        )
        if not file_path:
            return

        self._controller.load_video(file_path)
        self._video_path = Path(file_path)
        self._segment_manager.clear()
        self._refresh_segments_table()
        self.setWindowTitle(f"RallyPin - {Path(file_path).name}")
        self._status_label.setText("Video loaded. Use I/O to tag rallies.")
        self._refresh_ui_state()

    def _on_media_loaded_changed(self, loaded: bool) -> None:
        """Update control availability when media is loaded."""
        self._play_pause_button.setEnabled(loaded)
        self._position_slider.setEnabled(loaded)
        self._speed_combo.setEnabled(loaded)
        if loaded:
            self._controller.set_playback_rate(1.0)
        self._refresh_ui_state()

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        """Reflect current playback state in the play button text."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_pause_button.setText("Pause")
        else:
            self._play_pause_button.setText("Play")

    def _on_position_changed(self, position_ms: int) -> None:
        """Track and display updated playback position."""
        if not self._is_user_seeking:
            self._position_slider.setValue(position_ms)
        self._update_position_label(position_ms, self._controller.get_duration())

    def _on_duration_changed(self, duration_ms: int) -> None:
        """Set slider range and refresh time display when duration changes."""
        self._position_slider.setRange(0, max(0, duration_ms))
        self._update_position_label(self._controller.get_position(), duration_ms)

    def _on_slider_pressed(self) -> None:
        """Start temporary seek mode while user drags the slider."""
        self._is_user_seeking = True

    def _on_slider_released(self) -> None:
        """Seek to selected position and end temporary seek mode."""
        self._controller.set_position(self._position_slider.value())
        self._is_user_seeking = False

    def _on_slider_value_changed(self, value: int) -> None:
        """Live-update timestamp label while user scrubs."""
        if self._is_user_seeking:
            self._update_position_label(value, self._controller.get_duration())

    def _on_speed_changed(self, _index: int) -> None:
        """Apply selected speed to playback."""
        rate = float(self._speed_combo.currentData())
        self._controller.set_playback_rate(rate)

    def _pin_start(self) -> None:
        """Capture current playback position as rally start."""
        if not self._controller.is_media_loaded:
            return

        self._segment_manager.pin_start(self._controller.get_position())
        pending = self._segment_manager.pending_start_ms
        if pending is not None:
            self._pending_start_label.setText(
                f"Pending Start: {format_milliseconds(pending)}",
            )
            self._status_label.setText("Start pinned. Press O to mark rally end.")
        self._refresh_ui_state()

    def _pin_end(self) -> None:
        """Capture current playback position as rally end."""
        if not self._controller.is_media_loaded:
            return

        try:
            self._segment_manager.pin_end(self._controller.get_position())
        except ValueError as exc:
            self._show_error(str(exc))
            return

        self._refresh_segments_table()
        self._pending_start_label.setText("Pending Start: None")
        self._status_label.setText("Rally segment added.")
        self._refresh_ui_state()

    def _delete_selected_segments(self) -> None:
        """Delete selected segment rows from the table."""
        selected_rows = sorted({index.row() for index in self._segments_table.selectedIndexes()})
        if not selected_rows:
            return

        self._segment_manager.remove_indices(selected_rows)
        self._refresh_segments_table()
        self._status_label.setText("Selected segments deleted.")
        self._refresh_ui_state()

    def _clear_segments(self) -> None:
        """Clear all captured segments after confirmation."""
        if not self._segment_manager.segments:
            return

        response = QMessageBox.question(
            self,
            "Clear Segments",
            "Delete all pinned segments?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return

        self._segment_manager.clear()
        self._refresh_segments_table()
        self._pending_start_label.setText("Pending Start: None")
        self._status_label.setText("All segments cleared.")
        self._refresh_ui_state()

    def _edit_segment_row(self, row: int, _column: int) -> None:
        """Edit selected segment start/end timestamps through dialogs."""
        segments = self._segment_manager.segments
        if row < 0 or row >= len(segments):
            return
        existing_segment = segments[row]

        start_text, start_ok = QInputDialog.getText(
            self,
            "Edit Segment Start",
            "Start time (HH:MM:SS.mmm):",
            text=format_milliseconds(existing_segment.start_ms),
        )
        if not start_ok:
            return

        end_text, end_ok = QInputDialog.getText(
            self,
            "Edit Segment End",
            "End time (HH:MM:SS.mmm):",
            text=format_milliseconds(existing_segment.end_ms),
        )
        if not end_ok:
            return

        try:
            updated_segment = VideoSegment(
                start_ms=parse_timestamp_to_milliseconds(start_text),
                end_ms=parse_timestamp_to_milliseconds(end_text),
            )
            self._segment_manager.replace_segment(row, updated_segment)
        except ValueError as exc:
            self._show_error(str(exc))
            return

        self._refresh_segments_table()
        self._status_label.setText("Segment updated.")
        self._refresh_ui_state()

    def _start_export_concat(self) -> None:
        """Prompt for output file and run concatenated export."""
        if self._video_path is None:
            return

        output_file, _ = QFileDialog.getSaveFileName(
            self,
            "Save Concatenated Video",
            str(self._video_path.with_name(f"{self._video_path.stem}_rallies.mp4")),
            "MP4 Video (*.mp4)",
        )
        if not output_file:
            return
        self._launch_export_worker(mode="concat", output_path=Path(output_file))

    def _start_export_individual(self) -> None:
        """Prompt for output directory and run per-segment export."""
        if self._video_path is None:
            return

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            str(self._video_path.parent),
        )
        if not output_dir:
            return
        self._launch_export_worker(mode="individual", output_path=Path(output_dir))

    def _launch_export_worker(self, mode: str, output_path: Path) -> None:
        """Create and start export worker thread."""
        if self._video_path is None:
            return
        if not self._segment_manager.segments:
            self._show_error("No segments pinned for export.")
            return

        self._export_worker = ExportWorker(
            input_video=self._video_path,
            segments=self._segment_manager.segments,
            mode=mode,
            output_path=output_path,
            parent=self,
        )
        self._export_worker.completed.connect(self._on_export_completed)
        self._export_worker.failed.connect(self._on_export_failed)
        self._export_worker.finished.connect(self._on_export_finished)
        self._status_label.setText("Export in progress...")
        self._refresh_ui_state(is_exporting=True)
        self._export_worker.start()

    def _on_export_completed(self, message: str) -> None:
        """Display export success message."""
        self._status_label.setText("Export completed successfully.")
        QMessageBox.information(self, "Export Complete", message)

    def _on_export_failed(self, message: str) -> None:
        """Display export error message."""
        self._status_label.setText("Export failed.")
        self._show_error(message)

    def _on_export_finished(self) -> None:
        """Reset worker state and re-enable UI controls."""
        self._export_worker = None
        self._refresh_ui_state()

    def _refresh_segments_table(self) -> None:
        """Render all segments in the table widget."""
        segments = self._segment_manager.segments
        self._segments_table.setRowCount(len(segments))
        for row, segment in enumerate(segments):
            self._segments_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self._segments_table.setItem(row, 1, QTableWidgetItem(format_milliseconds(segment.start_ms)))
            self._segments_table.setItem(row, 2, QTableWidgetItem(format_milliseconds(segment.end_ms)))
            self._segments_table.setItem(row, 3, QTableWidgetItem(format_milliseconds(segment.duration_ms)))

    def _refresh_ui_state(self, is_exporting: bool | None = None) -> None:
        """Enable/disable controls based on media, segment, and export states."""
        exporting = is_exporting if is_exporting is not None else self._export_worker is not None
        has_video = self._controller.is_media_loaded
        has_segments = bool(self._segment_manager.segments)
        has_pending = self._segment_manager.pending_start_ms is not None

        self._open_button.setEnabled(not exporting)
        self._play_pause_button.setEnabled(has_video and not exporting)
        self._position_slider.setEnabled(has_video and not exporting)
        self._speed_combo.setEnabled(has_video and not exporting)
        self._pin_start_button.setEnabled(has_video and not exporting)
        self._pin_end_button.setEnabled(has_video and has_pending and not exporting)
        self._delete_segment_button.setEnabled(has_segments and not exporting)
        self._clear_segments_button.setEnabled((has_segments or has_pending) and not exporting)
        self._export_concat_button.setEnabled(has_video and has_segments and not exporting)
        self._export_individual_button.setEnabled(has_video and has_segments and not exporting)
        self._segments_table.setEnabled(not exporting)
        self._shortcut_pin_start.setEnabled(has_video and not exporting)
        self._shortcut_pin_end.setEnabled(has_video and has_pending and not exporting)

    def _update_position_label(self, position_ms: int, duration_ms: int) -> None:
        """Render elapsed and total times in a single label."""
        current = format_milliseconds(position_ms)
        total = format_milliseconds(duration_ms)
        self._position_label.setText(f"{current} / {total}")

    def _show_error(self, message: str) -> None:
        """Display a media or runtime error dialog."""
        QMessageBox.critical(self, "RallyPin Error", message)

