"""Main application window for RallyPin."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from PyQt6.QtCore import QSettings, QSize, QStandardPaths, Qt, QTimer
from PyQt6.QtGui import QAction, QCloseEvent, QKeySequence, QResizeEvent, QShortcut
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from rallypin.core.models import VideoSegment
from rallypin.core.project_store import ProjectFileError, RallyProject, load_project, save_project
from rallypin.core.segment_manager import SegmentManager
from rallypin.core.tag_utils import sanitize_tag_for_filename
from rallypin.core.time_utils import format_milliseconds, parse_timestamp_to_milliseconds
from rallypin.core.video_player_controller import VideoPlayerController
from rallypin.ui.export_worker import ExportWorker
from rallypin.ui.segment_table import SegmentTable
from rallypin.ui.shortcut_help import shortcut_help_html
from rallypin.ui.video_display import AspectFitVideoArea


class MainWindow(QMainWindow):
    """Keyboard-first workspace for marking and exporting badminton rallies."""

    PLAYBACK_SPEEDS: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
    SEEK_STEP_MS = 2_000
    COARSE_SEEK_STEP_MS = 10_000
    VIDEO_LAYOUT_MIN_PERCENT = 30
    VIDEO_LAYOUT_MAX_PERCENT = 85
    VIDEO_LAYOUT_DEFAULT_PERCENT = 58

    def __init__(self) -> None:
        """Create application state, widgets, actions, and event bindings."""
        super().__init__()
        self.resize(1280, 800)

        self._settings = QSettings()
        self._controller = VideoPlayerController(self)
        self._segment_manager = SegmentManager()
        self._is_user_seeking = False
        self._video_path: Path | None = None
        self._project_path: Path | None = None
        self._export_worker: ExportWorker | None = None
        self._dirty = False
        self._layout_percent = self._read_layout_percent()
        self._applying_layout_slider = False
        self._shortcuts: list[QShortcut] = []
        self._table_is_editing = False

        self._create_widgets()
        self._create_actions()
        self._build_layout()
        self._build_menus()
        self._bind_events()
        self._create_shortcuts()
        self._restore_window_state()
        self._refresh_segments_table()
        self._refresh_ui_state()
        self._update_window_title()

        QTimer.singleShot(0, self._offer_recovery_if_available)

    # ---- construction -------------------------------------------------

    def _create_widgets(self) -> None:
        """Create all persistent child widgets."""
        self._video_display = AspectFitVideoArea(self)
        self._controller.set_video_output(self._video_display.video_widget)

        self._open_button = QPushButton("Open video (Ctrl+O)", self)
        self._open_button.setObjectName("primaryButton")
        self._play_pause_button = QPushButton("Play (Space)", self)
        self._mute_button = QPushButton("Mute (M)", self)

        self._position_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._position_slider.setRange(0, 0)
        self._position_label = QLabel("00:00:00.000 / 00:00:00.000", self)
        self._position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._speed_label = QLabel("Speed", self)
        self._speed_combo = QComboBox(self)
        for speed in self.PLAYBACK_SPEEDS:
            self._speed_combo.addItem(f"{speed:.2f}x", speed)
        self._speed_combo.setCurrentText("1.00x")

        self._seek_back_button = QPushButton("-2 sec (Left)", self)
        self._seek_forward_button = QPushButton("+2 sec (Right)", self)
        self._seek_back_button.setToolTip("Seek backward 2 seconds. Hold Shift for 10 seconds.")
        self._seek_forward_button.setToolTip("Seek forward 2 seconds. Hold Shift for 10 seconds.")

        self._pin_start_button = QPushButton("Pin start (I)", self)
        self._pin_end_button = QPushButton("Pin end (O)", self)
        self._undo_button = QPushButton("Undo (Ctrl+Z)", self)
        self._remove_last_button = QPushButton("Remove last (Backspace)", self)
        self._delete_segment_button = QPushButton("Delete selected", self)
        self._clear_segments_button = QPushButton("Clear all", self)

        self._segments_table = SegmentTable(self)

        self._pending_start_label = QLabel("No start pinned", self)
        self._pending_start_label.setStyleSheet("color: #93c5fd; font-weight: 600;")
        self._shortcut_hint_label = QLabel(
            "I: start   O: end   Space: play/pause   N: tags   F1: all shortcuts",
            self,
        )
        self._shortcut_hint_label.setStyleSheet("color: #94a3b8;")

        self._layout_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._layout_slider.setRange(
            self.VIDEO_LAYOUT_MIN_PERCENT,
            self.VIDEO_LAYOUT_MAX_PERCENT,
        )
        self._layout_slider.setValue(self._layout_percent)
        self._layout_slider.setToolTip("Adjust the space used by the video and rally list.")

        self._export_tag_label = QLabel("Export", self)
        self._export_tag_combo = QComboBox(self)
        self._export_tag_combo.setMinimumWidth(190)
        self._export_concat_button = QPushButton("Play-by-play video (Ctrl+E)", self)
        self._export_concat_button.setObjectName("playByPlayButton")
        self._export_individual_button = QPushButton("Individual clips", self)

        self._status_label = QLabel("Open a video to start marking rallies.", self)
        self._status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._export_progress = QProgressBar(self)
        self._export_progress.setRange(0, 100)
        self._export_progress.setFixedWidth(240)
        self._export_progress.hide()
        self._cancel_export_button = QPushButton("Cancel export", self)
        self._cancel_export_button.hide()

    def _create_actions(self) -> None:
        """Create menu actions and standard keyboard accelerators."""
        self._open_video_action = QAction("Open &video...", self)
        self._open_video_action.setShortcut(QKeySequence.StandardKey.Open)
        self._open_video_action.triggered.connect(self._open_video)

        self._open_project_action = QAction("Open &project...", self)
        self._open_project_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self._open_project_action.triggered.connect(self._open_project)

        self._save_project_action = QAction("&Save project", self)
        self._save_project_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_project_action.triggered.connect(lambda: self._save_project())

        self._save_project_as_action = QAction("Save project &as...", self)
        self._save_project_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self._save_project_as_action.triggered.connect(lambda: self._save_project(force_as=True))

        self._export_concat_action = QAction("Export &play-by-play video...", self)
        self._export_concat_action.setShortcut(QKeySequence("Ctrl+E"))
        self._export_concat_action.triggered.connect(self._start_export_concat)

        self._export_individual_action = QAction("Export &individual clips...", self)
        self._export_individual_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self._export_individual_action.triggered.connect(self._start_export_individual)

        self._exit_action = QAction("E&xit", self)
        self._exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self._exit_action.triggered.connect(self.close)

        self._undo_action = QAction("&Undo timeline change", self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.triggered.connect(self._undo_last_change)

        self._delete_action = QAction("&Delete selected rallies", self)
        self._delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        self._delete_action.triggered.connect(self._delete_selected_segments)

        self._jump_action = QAction("&Jump to selected rally", self)
        self._jump_action.setShortcuts([QKeySequence("Return"), QKeySequence("Enter")])
        self._jump_action.triggered.connect(self._jump_to_selected_segment)

        self._edit_timing_action = QAction("Edit rally &timing...", self)
        self._edit_timing_action.setShortcut(QKeySequence("E"))
        self._edit_timing_action.triggered.connect(self._edit_selected_timing)

        self._clear_action = QAction("&Clear timeline", self)
        self._clear_action.setShortcut(QKeySequence("Ctrl+Shift+Delete"))
        self._clear_action.triggered.connect(self._clear_segments)

        self._focus_filter_action = QAction("Choose export &filter", self)
        self._focus_filter_action.setShortcut(QKeySequence("Ctrl+F"))
        self._focus_filter_action.triggered.connect(self._focus_export_filter)

        self._shortcuts_action = QAction("&Keyboard shortcuts", self)
        self._shortcuts_action.setShortcut(QKeySequence.StandardKey.HelpContents)
        self._shortcuts_action.triggered.connect(self._show_shortcuts)

        self._about_action = QAction("&About RallyPin", self)
        self._about_action.triggered.connect(self._show_about)

    def _build_layout(self) -> None:
        """Compose the video, timeline, export, and status areas."""
        playback_layout = QHBoxLayout()
        playback_layout.addWidget(self._open_button)
        playback_layout.addWidget(self._play_pause_button)
        playback_layout.addWidget(self._seek_back_button)
        playback_layout.addWidget(self._seek_forward_button)
        playback_layout.addWidget(self._speed_label)
        playback_layout.addWidget(self._speed_combo)
        playback_layout.addWidget(self._mute_button)
        playback_layout.addStretch(1)

        layout_slider_row = QHBoxLayout()
        layout_slider_row.addWidget(QLabel("Video space", self))
        layout_slider_row.addWidget(self._layout_slider, stretch=1)

        video_panel = QWidget(self)
        video_layout = QVBoxLayout(video_panel)
        video_layout.setContentsMargins(10, 10, 10, 4)
        video_layout.setSpacing(6)
        video_layout.addWidget(self._video_display, stretch=1)
        video_layout.addWidget(self._position_slider)
        video_layout.addWidget(self._position_label)
        video_layout.addLayout(playback_layout)
        video_layout.addWidget(self._pending_start_label)
        video_layout.addWidget(self._shortcut_hint_label)
        video_layout.addLayout(layout_slider_row)

        tagging_layout = QHBoxLayout()
        tagging_layout.addWidget(self._pin_start_button)
        tagging_layout.addWidget(self._pin_end_button)
        tagging_layout.addWidget(self._undo_button)
        tagging_layout.addWidget(self._remove_last_button)
        tagging_layout.addWidget(self._delete_segment_button)
        tagging_layout.addWidget(self._clear_segments_button)
        tagging_layout.addStretch(1)

        export_layout = QHBoxLayout()
        export_layout.addWidget(self._export_tag_label)
        export_layout.addWidget(self._export_tag_combo)
        export_layout.addWidget(self._export_concat_button)
        export_layout.addWidget(self._export_individual_button)
        export_layout.addStretch(1)

        status_layout = QHBoxLayout()
        status_layout.addWidget(self._status_label, stretch=1)
        status_layout.addWidget(self._export_progress)
        status_layout.addWidget(self._cancel_export_button)

        bottom_panel = QWidget(self)
        bottom_layout = QVBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(10, 4, 10, 8)
        bottom_layout.setSpacing(7)
        bottom_layout.addWidget(self._segments_table, stretch=1)
        bottom_layout.addLayout(tagging_layout)
        bottom_layout.addLayout(export_layout)
        bottom_layout.addLayout(status_layout)

        self._main_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self._main_splitter.addWidget(video_panel)
        self._main_splitter.addWidget(bottom_panel)
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setCollapsible(0, False)
        self._main_splitter.setCollapsible(1, False)
        self._main_splitter.setHandleWidth(5)

        container = QWidget(self)
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self._main_splitter)
        self.setCentralWidget(container)
        self._apply_layout_slider(self._layout_percent)

    def _build_menus(self) -> None:
        """Build a discoverable mouse-accessible menu bar."""
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self._open_video_action)
        file_menu.addAction(self._open_project_action)
        file_menu.addSeparator()
        file_menu.addAction(self._save_project_action)
        file_menu.addAction(self._save_project_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self._export_concat_action)
        file_menu.addAction(self._export_individual_action)
        file_menu.addSeparator()
        file_menu.addAction(self._exit_action)

        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(self._undo_action)
        edit_menu.addAction(self._delete_action)
        edit_menu.addAction(self._jump_action)
        edit_menu.addAction(self._edit_timing_action)
        edit_menu.addAction(self._clear_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self._focus_filter_action)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self._shortcuts_action)
        help_menu.addAction(self._about_action)

    def _bind_events(self) -> None:
        """Connect widgets and controller signals."""
        self._open_button.clicked.connect(self._open_video)
        self._play_pause_button.clicked.connect(self._controller.toggle_play_pause)
        self._mute_button.clicked.connect(self._toggle_mute)
        self._seek_back_button.clicked.connect(lambda: self._seek_relative(-self.SEEK_STEP_MS))
        self._seek_forward_button.clicked.connect(lambda: self._seek_relative(self.SEEK_STEP_MS))
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)

        self._controller.position_changed.connect(self._on_position_changed)
        self._controller.duration_changed.connect(self._on_duration_changed)
        self._controller.playback_state_changed.connect(self._on_playback_state_changed)
        self._controller.media_loaded_changed.connect(self._on_media_loaded_changed)
        self._controller.video_size_changed.connect(self._on_video_size_changed)
        self._controller.error_occurred.connect(self._on_media_error)

        self._position_slider.sliderPressed.connect(self._on_slider_pressed)
        self._position_slider.sliderReleased.connect(self._on_slider_released)
        self._position_slider.valueChanged.connect(self._on_slider_value_changed)
        self._layout_slider.valueChanged.connect(self._apply_layout_slider)
        self._main_splitter.splitterMoved.connect(self._on_splitter_moved)

        self._pin_start_button.clicked.connect(self._pin_start)
        self._pin_end_button.clicked.connect(self._pin_end)
        self._undo_button.clicked.connect(self._undo_last_change)
        self._remove_last_button.clicked.connect(self._remove_last_segment)
        self._delete_segment_button.clicked.connect(self._delete_selected_segments)
        self._clear_segments_button.clicked.connect(self._clear_segments)
        self._segments_table.cellDoubleClicked.connect(self._edit_segment_row)
        self._segments_table.tags_changed.connect(self._on_segment_tags_changed)
        self._segments_table.tag_validation_failed.connect(self._show_error)
        self._segments_table.editing_state_changed.connect(self._on_table_editing_changed)
        self._segments_table.itemSelectionChanged.connect(self._refresh_ui_state)
        app = QApplication.instance()
        if app is not None:
            app.focusChanged.connect(self._on_focus_changed)

        self._export_concat_button.clicked.connect(self._start_export_concat)
        self._export_individual_button.clicked.connect(self._start_export_individual)
        self._cancel_export_button.clicked.connect(self._cancel_export)

    def _create_shortcuts(self) -> None:
        """Register the high-frequency single-key editing workflow."""
        self._shortcut_pin_start = self._add_shortcut("I", self._pin_start)
        self._shortcut_pin_end = self._add_shortcut("O", self._pin_end)
        self._shortcut_play_pause = self._add_shortcut("Space", self._toggle_play_pause)
        self._shortcut_play_pause_alt = self._add_shortcut("K", self._toggle_play_pause)
        self._shortcut_seek_back = self._add_shortcut("Left", self._seek_backward)
        self._shortcut_seek_forward = self._add_shortcut("Right", self._seek_forward)
        self._shortcut_seek_back_coarse = self._add_shortcut(
            "Shift+Left",
            self._seek_backward_coarse,
        )
        self._shortcut_seek_forward_coarse = self._add_shortcut(
            "Shift+Right",
            self._seek_forward_coarse,
        )
        self._shortcut_speed_down = self._add_shortcut("[", self._decrease_speed)
        self._shortcut_speed_up = self._add_shortcut("]", self._increase_speed)
        self._shortcut_mute = self._add_shortcut("M", self._toggle_mute)
        self._shortcut_edit_tags = self._add_shortcut("N", self._edit_segment_tags)
        self._shortcut_remove_last = self._add_shortcut("Backspace", self._remove_last_segment)
        self._shortcut_cancel_pending = self._add_shortcut("Escape", self._cancel_pending_start)

    def _add_shortcut(self, keys: str, callback) -> QShortcut:  # noqa: ANN001
        """Create a non-repeating window shortcut and retain its owner."""
        shortcut = QShortcut(QKeySequence(keys), self)
        shortcut.setAutoRepeat(False)
        shortcut.activated.connect(callback)
        self._shortcuts.append(shortcut)
        return shortcut

    # ---- files and session recovery ----------------------------------

    def _open_video(self) -> None:
        """Choose a source video and start a fresh timeline."""
        if not self._confirm_leave_dirty_session():
            return
        start_dir = str(self._settings.value("lastVideoDirectory", ""))
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open badminton video",
            start_dir,
            "Video files (*.mp4 *.mov *.mkv *.avi *.m4v *.webm);;All files (*)",
        )
        if not file_path:
            return

        path = Path(file_path).resolve()
        self._segment_manager.replace_all([])
        self._project_path = None
        self._dirty = False
        self._clear_recovery()
        self._load_video_source(path)
        self._refresh_segments_table()
        self._status_label.setText("Loading video...")

    def _open_project(self) -> None:
        """Load a saved RallyPin timeline and its referenced video."""
        if not self._confirm_leave_dirty_session():
            return
        start_dir = str(self._settings.value("lastProjectDirectory", ""))
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open RallyPin project",
            start_dir,
            "RallyPin projects (*.rallypin.json *.json)",
        )
        if not file_path:
            return

        project_path = Path(file_path).resolve()
        try:
            project = load_project(project_path)
        except ProjectFileError as exc:
            self._show_error(str(exc))
            return

        resolved = self._resolve_missing_project_video(project)
        if resolved is None:
            return
        video_path, relocated = resolved
        self._settings.setValue("lastProjectDirectory", str(project_path.parent))
        self._load_session(
            video_path=video_path,
            segments=list(project.segments),
            project_path=project_path,
            dirty=relocated,
        )
        self._status_label.setText(
            "Project loaded. Save it to keep the relocated video path."
            if relocated
            else "Project loaded.",
        )

    def _save_project(self, force_as: bool = False) -> bool:
        """Save the current timeline and return whether it succeeded."""
        if self._video_path is None:
            self._show_error("Open a video before saving a project.")
            return False

        project_path = None if force_as else self._project_path
        if project_path is None:
            suggested = self._video_path.with_suffix(".rallypin.json")
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save RallyPin project",
                str(suggested),
                "RallyPin projects (*.rallypin.json)",
            )
            if not file_path:
                return False
            project_path = Path(file_path)
            if not project_path.name.casefold().endswith(".rallypin.json"):
                if project_path.suffix.casefold() == ".json":
                    project_path = project_path.with_name(
                        f"{project_path.stem}.rallypin.json",
                    )
                else:
                    project_path = project_path.with_name(
                        f"{project_path.name}.rallypin.json",
                    )

        try:
            save_project(project_path, self._video_path, self._segment_manager.segments)
        except ProjectFileError as exc:
            self._show_error(str(exc))
            return False

        self._project_path = project_path.resolve()
        self._settings.setValue("lastProjectDirectory", str(self._project_path.parent))
        self._dirty = False
        self._clear_recovery()
        self._update_window_title()
        self._status_label.setText(f"Project saved: {self._project_path.name}")
        self._refresh_ui_state()
        return True

    def _load_session(
        self,
        video_path: Path,
        segments: list[VideoSegment],
        project_path: Path | None,
        dirty: bool,
    ) -> None:
        """Replace the current session with loaded or recovered data."""
        self._segment_manager.replace_all(segments)
        self._project_path = project_path
        self._dirty = dirty
        self._load_video_source(video_path)
        self._refresh_segments_table()
        self._update_pending_label()
        self._update_window_title()
        self._refresh_ui_state()
        if dirty:
            self._mark_dirty()
        else:
            self._clear_recovery()

    def _load_video_source(self, path: Path) -> None:
        """Remember and ask the player to load a validated local path."""
        self._video_path = path.resolve()
        self._settings.setValue("lastVideoDirectory", str(self._video_path.parent))
        self._controller.load_video(str(self._video_path))
        self._update_window_title()
        self._refresh_ui_state()

    def _resolve_missing_project_video(
        self,
        project: RallyProject,
    ) -> tuple[Path, bool] | None:
        """Ask the user to relink a project whose video has moved."""
        if project.video_path.is_file():
            return project.video_path, False

        response = QMessageBox.question(
            self,
            "Video not found",
            f"The project video is missing:\n{project.video_path}\n\nLocate it now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if response != QMessageBox.StandardButton.Yes:
            return None
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Locate project video",
            str(project.video_path.parent),
            "Video files (*.mp4 *.mov *.mkv *.avi *.m4v *.webm);;All files (*)",
        )
        if not file_path:
            return None
        return Path(file_path).resolve(), True

    def _mark_dirty(self) -> None:
        """Mark timeline changes and write a crash-recovery snapshot."""
        if self._video_path is None:
            return
        self._dirty = True
        self._update_window_title()
        try:
            save_project(
                self._recovery_path(),
                self._video_path,
                self._segment_manager.segments,
            )
        except ProjectFileError:
            self._status_label.setText(
                "Timeline changed, but the recovery copy could not be saved."
            )
        self._refresh_ui_state()

    def _offer_recovery_if_available(self) -> None:
        """Offer to restore the most recent unsaved timeline after a crash."""
        recovery_path = self._recovery_path()
        if not recovery_path.is_file() or self._video_path is not None:
            return
        try:
            project = load_project(recovery_path)
        except ProjectFileError:
            self._clear_recovery()
            return
        if not project.video_path.is_file():
            self._clear_recovery()
            return

        response = QMessageBox.question(
            self,
            "Recover unsaved work",
            f"RallyPin found an unsaved timeline for:\n{project.video_path.name}\n\nRecover it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if response == QMessageBox.StandardButton.Yes:
            self._load_session(
                video_path=project.video_path,
                segments=list(project.segments),
                project_path=None,
                dirty=True,
            )
            self._status_label.setText("Unsaved timeline recovered. Press Ctrl+S to keep it.")
        else:
            self._clear_recovery()

    def _confirm_leave_dirty_session(self) -> bool:
        """Ask whether to save unsaved timeline edits before replacing them."""
        if not self._dirty:
            return True
        response = QMessageBox.warning(
            self,
            "Unsaved timeline",
            "Save your RallyPin project before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if response == QMessageBox.StandardButton.Cancel:
            return False
        if response == QMessageBox.StandardButton.Save:
            return self._save_project()
        return True

    def _recovery_path(self) -> Path:
        """Return the per-user recovery file location."""
        location = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation,
        )
        base = Path(location) if location else Path.home() / ".rallypin"
        return base / "recovery.rallypin.json"

    def _clear_recovery(self) -> None:
        """Remove the recovery snapshot after save or explicit discard."""
        with suppress(OSError):
            self._recovery_path().unlink(missing_ok=True)

    # ---- playback -----------------------------------------------------

    def _on_media_loaded_changed(self, loaded: bool) -> None:
        """Refresh controls after Qt accepts or rejects the source."""
        if loaded:
            self._speed_combo.setCurrentText("1.00x")
            self._controller.set_playback_rate(1.0)
            self._status_label.setText("Ready. Press I at rally start and O at rally end.")
        self._refresh_ui_state()

    def _on_media_error(self, message: str) -> None:
        """Show a player error without discarding the saved timeline."""
        self._status_label.setText("The video could not be loaded.")
        self._refresh_ui_state()
        self._show_error(message)

    def _on_video_size_changed(self, size: QSize) -> None:
        """Preserve the source aspect ratio in the video panel."""
        self._video_display.set_aspect_ratio(size.width(), size.height())

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        """Keep the playback button label synchronized."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_pause_button.setText("Pause (Space)")
        else:
            self._play_pause_button.setText("Play (Space)")

    def _on_position_changed(self, position_ms: int) -> None:
        """Update the slider and time readout during playback."""
        if not self._is_user_seeking:
            self._position_slider.setValue(position_ms)
        self._update_position_label(position_ms, self._controller.get_duration())

    def _on_duration_changed(self, duration_ms: int) -> None:
        """Update the seek range when media metadata arrives."""
        self._position_slider.setRange(0, max(0, duration_ms))
        self._update_position_label(self._controller.get_position(), duration_ms)

    def _on_slider_pressed(self) -> None:
        self._is_user_seeking = True

    def _on_slider_released(self) -> None:
        self._controller.set_position(self._position_slider.value())
        self._is_user_seeking = False

    def _on_slider_value_changed(self, value: int) -> None:
        if self._is_user_seeking:
            self._update_position_label(value, self._controller.get_duration())

    def _toggle_play_pause(self) -> None:
        if not self._focus_is_text_entry():
            self._controller.toggle_play_pause()

    def _seek_relative(self, delta_ms: int) -> None:
        if not self._focus_is_text_entry():
            self._controller.seek_relative(delta_ms)

    def _seek_backward(self) -> None:
        self._seek_relative(-self.SEEK_STEP_MS)

    def _seek_forward(self) -> None:
        self._seek_relative(self.SEEK_STEP_MS)

    def _seek_backward_coarse(self) -> None:
        self._seek_relative(-self.COARSE_SEEK_STEP_MS)

    def _seek_forward_coarse(self) -> None:
        self._seek_relative(self.COARSE_SEEK_STEP_MS)

    def _on_speed_changed(self, _index: int) -> None:
        data = self._speed_combo.currentData()
        if data is not None:
            self._controller.set_playback_rate(float(data))

    def _decrease_speed(self) -> None:
        if self._focus_is_text_entry():
            return
        self._speed_combo.setCurrentIndex(max(0, self._speed_combo.currentIndex() - 1))

    def _increase_speed(self) -> None:
        if self._focus_is_text_entry():
            return
        self._speed_combo.setCurrentIndex(
            min(self._speed_combo.count() - 1, self._speed_combo.currentIndex() + 1),
        )

    def _toggle_mute(self) -> None:
        if self._focus_is_text_entry():
            return
        muted = self._controller.toggle_muted()
        self._mute_button.setText("Unmute (M)" if muted else "Mute (M)")

    # ---- rally timeline ----------------------------------------------

    def _pin_start(self) -> None:
        """Capture the current playback position as a rally start."""
        if self._focus_is_text_entry() or not self._controller.is_media_loaded:
            return
        self._segment_manager.pin_start(self._controller.get_position())
        self._update_pending_label()
        self._status_label.setText("Start pinned. Press O at the end of the rally.")
        self._refresh_ui_state()

    def _pin_end(self) -> None:
        """Complete the pending rally at the current playback position."""
        if self._focus_is_text_entry() or not self._controller.is_media_loaded:
            return
        try:
            self._segment_manager.pin_end(self._controller.get_position())
        except ValueError as exc:
            self._show_error(str(exc))
            return

        self._refresh_segments_table()
        self._segments_table.select_last()
        self._update_pending_label()
        self._status_label.setText("Rally added. Keep playing and press I for the next one.")
        self._mark_dirty()

    def _cancel_pending_start(self) -> None:
        """Cancel a pending start without changing completed rallies."""
        if self._focus_is_text_entry():
            return
        if self._segment_manager.cancel_pending():
            self._update_pending_label()
            self._status_label.setText("Pending start cancelled.")
            self._refresh_ui_state()

    def _undo_last_change(self) -> None:
        """Restore the timeline before its most recent modification."""
        if self._focus_is_text_entry():
            return
        before = self._segment_manager.segments
        if not self._segment_manager.undo():
            return
        self._refresh_segments_table()
        self._update_pending_label()
        self._status_label.setText("Last timeline change undone.")
        if self._segment_manager.segments != before:
            self._mark_dirty()
        else:
            self._refresh_ui_state()

    def _remove_last_segment(self) -> None:
        """Remove the final completed rally."""
        if self._focus_is_text_entry() or not self._segment_manager.remove_last():
            return
        self._refresh_segments_table()
        self._status_label.setText("Last rally removed. Ctrl+Z restores it.")
        self._mark_dirty()

    def _delete_selected_segments(self) -> None:
        """Delete selected rows and retain an undo snapshot."""
        if self._focus_is_text_entry():
            return
        rows = self._segments_table.selected_rows()
        if not rows:
            return
        self._segment_manager.remove_indices(rows)
        self._refresh_segments_table()
        self._status_label.setText("Selected rallies deleted. Ctrl+Z restores them.")
        self._mark_dirty()

    def _clear_segments(self) -> None:
        """Clear completed rallies and any pending start after confirmation."""
        has_segments = bool(self._segment_manager.segments)
        has_pending = self._segment_manager.pending_start_ms is not None
        if not has_segments and not has_pending:
            return
        response = QMessageBox.question(
            self,
            "Clear timeline",
            "Clear all rallies and the pending start?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        self._segment_manager.clear()
        self._refresh_segments_table()
        self._update_pending_label()
        self._status_label.setText("Timeline cleared. Ctrl+Z restores it.")
        if has_segments:
            self._mark_dirty()
        else:
            self._refresh_ui_state()

    def _edit_segment_tags(self) -> None:
        """Start inline tag editing on the selected or last rally."""
        if not self._focus_is_text_entry():
            self._segments_table.begin_tag_edit()

    def _on_segment_tags_changed(self, row: int, tags: tuple[str, ...]) -> None:
        """Persist a normalized tag edit in the timeline model."""
        segments = self._segment_manager.segments
        if not 0 <= row < len(segments) or segments[row].tags == tags:
            return
        self._segment_manager.set_segment_tags(row, tags)
        self._rebuild_export_tag_combo()
        self._status_label.setText("Tags updated.")
        self._mark_dirty()

    def _edit_segment_row(self, row: int, column: int) -> None:
        """Edit start and end timestamps when a time cell is double-clicked."""
        if column not in (1, 2):
            return
        segments = self._segment_manager.segments
        if not 0 <= row < len(segments):
            return
        existing = segments[row]
        start_text, start_ok = QInputDialog.getText(
            self,
            "Edit rally start",
            "Start time (HH:MM:SS.mmm)",
            text=format_milliseconds(existing.start_ms),
        )
        if not start_ok:
            return
        end_text, end_ok = QInputDialog.getText(
            self,
            "Edit rally end",
            "End time (HH:MM:SS.mmm)",
            text=format_milliseconds(existing.end_ms),
        )
        if not end_ok:
            return
        try:
            updated = VideoSegment(
                start_ms=parse_timestamp_to_milliseconds(start_text),
                end_ms=parse_timestamp_to_milliseconds(end_text),
                tags=existing.tags,
            )
            duration_ms = self._controller.get_duration()
            if duration_ms > 0 and updated.end_ms > duration_ms:
                raise ValueError("Rally end cannot be later than the end of the video.")
            self._segment_manager.replace_segment(row, updated)
        except (TypeError, ValueError) as exc:
            self._show_error(str(exc))
            return
        self._refresh_segments_table()
        self._segments_table.selectRow(row)
        self._status_label.setText("Rally timing updated.")
        self._mark_dirty()

    def _edit_selected_timing(self) -> None:
        """Open timestamp editing for the selected or final rally."""
        if self._focus_is_text_entry():
            return
        row = self._segments_table.selected_or_last_row()
        if row is not None:
            self._edit_segment_row(row, 1)

    def _jump_to_selected_segment(self) -> None:
        """Seek to the start of the selected rally."""
        if self._focus_is_text_entry():
            return
        row = self._segments_table.selected_or_last_row()
        segments = self._segment_manager.segments
        if row is None or not 0 <= row < len(segments):
            return
        self._controller.set_position(segments[row].start_ms)
        self._segments_table.selectRow(row)
        self._status_label.setText(f"Jumped to rally {row + 1}.")

    def _focus_export_filter(self) -> None:
        """Move keyboard focus to the export filter and open its choices."""
        if not self._export_tag_combo.isEnabled():
            return
        self._export_tag_combo.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._export_tag_combo.showPopup()

    # ---- export -------------------------------------------------------

    def _start_export_concat(self) -> None:
        """Choose a file and export the filtered play-by-play timeline."""
        segments = self._validated_export_segments()
        if segments is None or self._video_path is None:
            return
        output_file, _ = QFileDialog.getSaveFileName(
            self,
            "Save play-by-play video",
            str(self._video_path.parent / f"{self._default_export_basename()}.mp4"),
            "MP4 video (*.mp4)",
        )
        if not output_file:
            return
        output_path = Path(output_file)
        if output_path.suffix.casefold() != ".mp4":
            output_path = output_path.with_suffix(".mp4")
        if output_path.resolve() == self._video_path.resolve():
            self._show_error(
                "Choose a different filename. RallyPin will not overwrite the source video."
            )
            return
        self._launch_export_worker("concat", output_path, segments)

    def _start_export_individual(self) -> None:
        """Choose a directory and export every filtered rally."""
        segments = self._validated_export_segments()
        if segments is None or self._video_path is None:
            return
        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Choose a folder for rally clips",
            str(self._video_path.parent),
        )
        if not output_dir:
            return
        self._launch_export_worker("individual", Path(output_dir), segments)

    def _validated_export_segments(self) -> list[VideoSegment] | None:
        """Return filtered segments after checking video bounds."""
        segments = self._segments_for_current_export_filter()
        if not segments:
            self._show_error("No rallies match the selected export filter.")
            return None
        duration_ms = self._controller.get_duration()
        invalid_index = next(
            (
                index
                for index, segment in enumerate(segments, start=1)
                if segment.end_ms > duration_ms
            ),
            None,
        )
        if duration_ms > 0 and invalid_index is not None:
            self._show_error(
                f"Rally {invalid_index} ends after the source video. Edit its timestamps before export.",
            )
            return None
        return segments

    def _launch_export_worker(
        self,
        mode: str,
        output_path: Path,
        segments: list[VideoSegment],
    ) -> None:
        """Start an interruptible background export."""
        if self._video_path is None or self._export_worker is not None:
            return
        worker = ExportWorker(
            input_video=self._video_path,
            segments=segments,
            mode=mode,
            output_path=output_path,
            parent=self,
        )
        worker.completed.connect(self._on_export_completed)
        worker.failed.connect(self._on_export_failed)
        worker.cancelled.connect(self._on_export_cancelled)
        worker.progress_changed.connect(self._on_export_progress)
        worker.finished.connect(self._on_export_finished)
        self._export_worker = worker

        self._export_progress.setValue(0)
        self._export_progress.show()
        self._cancel_export_button.setEnabled(True)
        self._cancel_export_button.setText("Cancel export")
        self._cancel_export_button.show()
        self._status_label.setText("Preparing export...")
        self._refresh_ui_state()
        worker.start()

    def _cancel_export(self) -> None:
        """Request cancellation and keep the UI informed while FFmpeg stops."""
        if self._export_worker is None:
            return
        self._cancel_export_button.setEnabled(False)
        self._cancel_export_button.setText("Cancelling...")
        self._status_label.setText("Cancelling export...")
        self._export_worker.cancel()

    def _on_export_progress(self, percent: int, message: str) -> None:
        self._export_progress.setValue(percent)
        self._status_label.setText(message)

    def _on_export_completed(self, message: str) -> None:
        self._export_progress.setValue(100)
        self._status_label.setText("Export complete.")
        QMessageBox.information(self, "Export complete", message)

    def _on_export_failed(self, message: str) -> None:
        self._status_label.setText("Export failed. Existing files were left intact.")
        self._show_error(message)

    def _on_export_cancelled(self) -> None:
        self._status_label.setText("Export cancelled. Temporary files were removed.")

    def _on_export_finished(self) -> None:
        self._export_worker = None
        self._export_progress.hide()
        self._cancel_export_button.hide()
        self._refresh_ui_state()

    # ---- rendering and state -----------------------------------------

    def _refresh_segments_table(self) -> None:
        """Render the model and rebuild its export filters."""
        self._segments_table.render(self._segment_manager.segments)
        self._rebuild_export_tag_combo()

    def _rebuild_export_tag_combo(self) -> None:
        """Preserve the selected filter while rebuilding tag choices."""
        previous = self._export_tag_combo.currentData()
        self._export_tag_combo.blockSignals(True)
        self._export_tag_combo.clear()
        self._export_tag_combo.addItem("All rallies", None)
        self._export_tag_combo.addItem("Untagged only", "__untagged__")
        for tag in self._segment_manager.collect_unique_tags():
            self._export_tag_combo.addItem(f'Tag: "{tag}"', tag)
        for index in range(self._export_tag_combo.count()):
            if self._export_tag_combo.itemData(index) == previous:
                self._export_tag_combo.setCurrentIndex(index)
                break
        self._export_tag_combo.blockSignals(False)

    def _segments_for_current_export_filter(self) -> list[VideoSegment]:
        data = self._export_tag_combo.currentData()
        segments = self._segment_manager.segments
        if data is None:
            return segments
        if data == "__untagged__":
            return [segment for segment in segments if not segment.tags]
        return [segment for segment in segments if data in segment.tags]

    def _default_export_basename(self) -> str:
        if self._video_path is None:
            return "rallies"
        data = self._export_tag_combo.currentData()
        suffix = "rallies"
        if data == "__untagged__":
            suffix = "rallies_untagged"
        elif data is not None:
            suffix = f"rallies_{sanitize_tag_for_filename(str(data))}"
        return f"{self._video_path.stem}_{suffix}"

    def _refresh_ui_state(self) -> None:
        """Enable every button, action, and shortcut from current state."""
        exporting = self._export_worker is not None
        has_video = self._controller.is_media_loaded
        has_segments = bool(self._segment_manager.segments)
        has_pending = self._segment_manager.pending_start_ms is not None
        has_selection = bool(self._segments_table.selected_rows())
        accepts_global_keys = not self._focus_is_text_entry()

        self._open_button.setEnabled(not exporting)
        self._play_pause_button.setEnabled(has_video and not exporting)
        self._mute_button.setEnabled(has_video and not exporting)
        self._seek_back_button.setEnabled(has_video and not exporting)
        self._seek_forward_button.setEnabled(has_video and not exporting)
        self._position_slider.setEnabled(has_video and not exporting)
        self._speed_combo.setEnabled(has_video and not exporting)
        self._pin_start_button.setEnabled(has_video and not exporting)
        self._pin_end_button.setEnabled(has_video and has_pending and not exporting)
        self._undo_button.setEnabled(self._segment_manager.can_undo and not exporting)
        self._remove_last_button.setEnabled(has_segments and not exporting)
        self._delete_segment_button.setEnabled(has_selection and not exporting)
        self._clear_segments_button.setEnabled((has_segments or has_pending) and not exporting)
        self._segments_table.setEnabled(not exporting)
        self._export_tag_combo.setEnabled(has_segments and not exporting)
        self._export_concat_button.setEnabled(has_video and has_segments and not exporting)
        self._export_individual_button.setEnabled(has_video and has_segments and not exporting)

        self._open_video_action.setEnabled(not exporting)
        self._open_project_action.setEnabled(not exporting)
        self._save_project_action.setEnabled(self._video_path is not None and not exporting)
        self._save_project_as_action.setEnabled(self._video_path is not None and not exporting)
        self._export_concat_action.setEnabled(has_video and has_segments and not exporting)
        self._export_individual_action.setEnabled(has_video and has_segments and not exporting)
        self._undo_action.setEnabled(
            self._segment_manager.can_undo and not exporting and accepts_global_keys,
        )
        self._delete_action.setEnabled(has_selection and not exporting and accepts_global_keys)
        self._jump_action.setEnabled(
            has_video and has_segments and not exporting and accepts_global_keys,
        )
        self._edit_timing_action.setEnabled(
            has_segments and not exporting and accepts_global_keys,
        )
        self._clear_action.setEnabled((has_segments or has_pending) and not exporting)
        self._focus_filter_action.setEnabled(has_segments and not exporting)

        for shortcut in (
            self._shortcut_play_pause,
            self._shortcut_play_pause_alt,
            self._shortcut_seek_back,
            self._shortcut_seek_forward,
            self._shortcut_seek_back_coarse,
            self._shortcut_seek_forward_coarse,
            self._shortcut_speed_down,
            self._shortcut_speed_up,
            self._shortcut_mute,
            self._shortcut_pin_start,
        ):
            shortcut.setEnabled(has_video and not exporting and accepts_global_keys)
        self._shortcut_pin_end.setEnabled(
            has_video and has_pending and not exporting and accepts_global_keys,
        )
        self._shortcut_edit_tags.setEnabled(has_segments and not exporting and accepts_global_keys)
        self._shortcut_remove_last.setEnabled(
            has_segments and not exporting and accepts_global_keys,
        )
        self._shortcut_cancel_pending.setEnabled(
            has_pending and not exporting and accepts_global_keys,
        )

    def _update_pending_label(self) -> None:
        pending = self._segment_manager.pending_start_ms
        if pending is None:
            self._pending_start_label.setText("No start pinned")
        else:
            self._pending_start_label.setText(
                f"Start pinned at {format_milliseconds(pending)}. Press O to finish or Esc to cancel.",
            )

    def _update_position_label(self, position_ms: int, duration_ms: int) -> None:
        self._position_label.setText(
            f"{format_milliseconds(position_ms)} / {format_milliseconds(duration_ms)}",
        )

    def _update_window_title(self) -> None:
        video_name = self._video_path.name if self._video_path is not None else "No video"
        dirty_marker = "*" if self._dirty else ""
        self.setWindowTitle(f"{dirty_marker}{video_name} - RallyPin")

    def _focus_is_text_entry(self) -> bool:
        widget = QApplication.focusWidget()
        return self._table_is_editing or isinstance(widget, (QLineEdit, QComboBox))

    def _on_table_editing_changed(self, editing: bool) -> None:
        """Suspend single-key timeline shortcuts while tags are being typed."""
        self._table_is_editing = editing
        self._refresh_ui_state()

    def _on_focus_changed(self, _old, _current) -> None:  # noqa: ANN001
        """Release single-key shortcuts while a text field or combo is active."""
        self._refresh_ui_state()

    # ---- layout, help, and shutdown ----------------------------------

    def _apply_layout_slider(self, percent: int) -> None:
        """Allocate vertical space between the player and rally list."""
        percent = max(self.VIDEO_LAYOUT_MIN_PERCENT, min(self.VIDEO_LAYOUT_MAX_PERCENT, percent))
        self._layout_percent = percent
        if self._applying_layout_slider:
            return
        self._applying_layout_slider = True
        try:
            self._layout_slider.blockSignals(True)
            self._layout_slider.setValue(percent)
            self._layout_slider.blockSignals(False)
            total_height = max(1, self._main_splitter.height())
            video_height = max(250, round(total_height * percent / 100))
            list_height = max(180, total_height - video_height)
            self._main_splitter.setSizes([video_height, list_height])
        finally:
            self._applying_layout_slider = False

    def _on_splitter_moved(self, _position: int, _index: int) -> None:
        """Keep the layout slider synchronized with mouse dragging."""
        if self._applying_layout_slider:
            return
        sizes = self._main_splitter.sizes()
        total = sum(sizes)
        if total <= 0:
            return
        percent = round((sizes[0] / total) * 100)
        self._layout_percent = max(
            self.VIDEO_LAYOUT_MIN_PERCENT,
            min(self.VIDEO_LAYOUT_MAX_PERCENT, percent),
        )
        self._layout_slider.blockSignals(True)
        self._layout_slider.setValue(self._layout_percent)
        self._layout_slider.blockSignals(False)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_layout_slider(self._layout_percent)

    def _read_layout_percent(self) -> int:
        value = self._settings.value("videoLayoutPercent", self.VIDEO_LAYOUT_DEFAULT_PERCENT)
        try:
            return int(value)
        except (TypeError, ValueError):
            return self.VIDEO_LAYOUT_DEFAULT_PERCENT

    def _restore_window_state(self) -> None:
        geometry = self._settings.value("windowGeometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def _show_shortcuts(self) -> None:
        QMessageBox.information(self, "RallyPin keyboard shortcuts", shortcut_help_html())

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About RallyPin",
            "<h2>RallyPin</h2>"
            "<p>Cut the dead time between badminton rallies and export a clean play-by-play video.</p>"
            "<p>Your video and project stay on your computer.</p>",
        )

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "RallyPin", message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Protect active exports and unsaved timelines during shutdown."""
        if self._export_worker is not None:
            response = QMessageBox.question(
                self,
                "Export in progress",
                "Cancel the export and close RallyPin?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if response != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            worker = self._export_worker
            worker.cancel()
            if not worker.wait(5_000):
                self._show_error("The exporter is still stopping. Try closing again in a moment.")
                event.ignore()
                return
            self._export_worker = None

        if not self._confirm_leave_dirty_session():
            event.ignore()
            return
        if self._dirty:
            self._clear_recovery()

        self._settings.setValue("windowGeometry", self.saveGeometry())
        self._settings.setValue("videoLayoutPercent", self._layout_percent)
        event.accept()
