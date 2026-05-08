"""Controller abstraction around Qt multimedia playback."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer


class VideoPlayerController(QObject):
    """Encapsulates playback state and behavior for the UI layer."""

    position_changed = pyqtSignal(int)
    duration_changed = pyqtSignal(int)
    playback_state_changed = pyqtSignal(QMediaPlayer.PlaybackState)
    media_loaded_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize media player resources and event wiring."""
        super().__init__(parent)
        self._player: QMediaPlayer = QMediaPlayer(self)
        self._audio_output: QAudioOutput = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(1.0)

        self._is_media_loaded: bool = False
        self._player.positionChanged.connect(self.position_changed.emit)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self.playback_state_changed.emit)
        self._player.errorOccurred.connect(self._on_error_occurred)

    @property
    def media_player(self) -> QMediaPlayer:
        """Return the underlying Qt media player instance."""
        return self._player

    @property
    def is_media_loaded(self) -> bool:
        """Return whether a media source is currently loaded."""
        return self._is_media_loaded

    def load_video(self, file_path: str) -> None:
        """Load a local video file into the media player."""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            self.error_occurred.emit(f"Video file not found: {file_path}")
            return

        self._player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self._is_media_loaded = True
        self.media_loaded_changed.emit(True)

    def play(self) -> None:
        """Start video playback if media is loaded."""
        if not self._is_media_loaded:
            return
        self._player.play()

    def pause(self) -> None:
        """Pause playback."""
        self._player.pause()

    def toggle_play_pause(self) -> None:
        """Toggle between play and pause states."""
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
            return
        self.play()

    def set_position(self, position_ms: int) -> None:
        """Seek playback to a specific position in milliseconds."""
        if not self._is_media_loaded:
            return
        self._player.setPosition(max(0, position_ms))

    def set_playback_rate(self, rate: float) -> None:
        """Set playback speed multiplier."""
        if rate <= 0:
            self.error_occurred.emit("Playback rate must be greater than zero.")
            return
        self._player.setPlaybackRate(rate)

    def get_position(self) -> int:
        """Return current playback position in milliseconds."""
        return self._player.position()

    def get_duration(self) -> int:
        """Return media duration in milliseconds."""
        return self._player.duration()

    def _on_duration_changed(self, duration_ms: int) -> None:
        """Propagate duration changes to the UI and update load state."""
        self.duration_changed.emit(duration_ms)

    def _on_error_occurred(self, _error: QMediaPlayer.Error, error_text: str) -> None:
        """Forward media player errors to higher layers."""
        self.error_occurred.emit(error_text)

