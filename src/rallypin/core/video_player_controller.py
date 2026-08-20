"""Controller abstraction around Qt multimedia playback."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QSize, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer


class VideoPlayerController(QObject):
    """Encapsulates playback state and behavior for the UI layer."""

    position_changed = pyqtSignal(int)
    duration_changed = pyqtSignal(int)
    playback_state_changed = pyqtSignal(QMediaPlayer.PlaybackState)
    media_loaded_changed = pyqtSignal(bool)
    video_size_changed = pyqtSignal(QSize)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize media player resources and event wiring."""
        super().__init__(parent)
        self._player: QMediaPlayer = QMediaPlayer(self)
        self._audio_output: QAudioOutput = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(1.0)

        self._is_media_loaded: bool = False
        self._video_sink_wired: bool = False
        self._player.positionChanged.connect(self.position_changed.emit)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self.playback_state_changed.emit)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_error_occurred)

    @property
    def media_player(self) -> QMediaPlayer:
        """Return the underlying Qt media player instance."""
        return self._player

    @property
    def is_media_loaded(self) -> bool:
        """Return whether a media source is currently loaded."""
        return self._is_media_loaded

    def set_video_output(self, output) -> None:  # noqa: ANN001
        """Attach a video output widget and wire dimension change signals."""
        self._player.setVideoOutput(output)
        self._wire_video_sink()

    def load_video(self, file_path: str) -> None:
        """Load a local video file into the media player."""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            self.error_occurred.emit(f"Video file not found: {file_path}")
            return

        self._player.stop()
        self._set_media_loaded(False)
        self._player.setSource(QUrl.fromLocalFile(str(path.resolve())))

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
        duration_ms = self._player.duration()
        target = max(0, position_ms)
        if duration_ms > 0:
            target = min(duration_ms, target)
        self._player.setPosition(target)

    def seek_relative(self, delta_ms: int) -> None:
        """Seek by a delta in milliseconds, clamped to media bounds."""
        if not self._is_media_loaded:
            return
        duration_ms = self._player.duration()
        if duration_ms <= 0:
            return
        current = self._player.position()
        new_pos = max(0, min(duration_ms, current + delta_ms))
        self._player.setPosition(new_pos)

    def set_playback_rate(self, rate: float) -> None:
        """Set playback speed multiplier."""
        if rate <= 0:
            self.error_occurred.emit("Playback rate must be greater than zero.")
            return
        self._player.setPlaybackRate(rate)

    @property
    def is_muted(self) -> bool:
        """Return whether audio output is muted."""
        return self._audio_output.isMuted()

    def toggle_muted(self) -> bool:
        """Toggle audio mute state and return the new value."""
        muted = not self._audio_output.isMuted()
        self._audio_output.setMuted(muted)
        return muted

    def get_position(self) -> int:
        """Return current playback position in milliseconds."""
        return self._player.position()

    def get_duration(self) -> int:
        """Return media duration in milliseconds."""
        return self._player.duration()

    def _on_duration_changed(self, duration_ms: int) -> None:
        """Propagate duration changes to the UI and update load state."""
        self.duration_changed.emit(duration_ms)

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        """Only expose playback controls after Qt has accepted the source."""
        loaded_statuses = {
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        }
        if status in loaded_statuses:
            self._set_media_loaded(True)
        elif status in {
            QMediaPlayer.MediaStatus.NoMedia,
            QMediaPlayer.MediaStatus.InvalidMedia,
        }:
            self._set_media_loaded(False)

    def _set_media_loaded(self, loaded: bool) -> None:
        """Update and emit the load state only when it changes."""
        if self._is_media_loaded == loaded:
            return
        self._is_media_loaded = loaded
        self.media_loaded_changed.emit(loaded)

    def _wire_video_sink(self) -> None:
        """Connect to the video sink once a video output is attached."""
        if self._video_sink_wired:
            return

        sink = self._player.videoSink()
        if sink is None:
            return

        sink.videoSizeChanged.connect(self._on_sink_video_size_changed)
        self._video_sink_wired = True
        self._on_sink_video_size_changed()

    def _on_sink_video_size_changed(self) -> None:
        """Read video dimensions from the sink and forward them to the UI."""
        sink = self._player.videoSink()
        if sink is None:
            return
        size = sink.videoSize()
        if size.isValid() and size.width() > 0 and size.height() > 0:
            self.video_size_changed.emit(size)

    def _on_error_occurred(self, _error: QMediaPlayer.Error, error_text: str) -> None:
        """Forward media player errors to higher layers."""
        self._set_media_loaded(False)
        self.error_occurred.emit(error_text or "The selected video could not be opened.")
