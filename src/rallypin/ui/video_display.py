"""Video display area that fits footage to the available height."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QWidget


class AspectFitVideoArea(QWidget):
    """Centers video in the panel and scales it to fit the available height."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the display surface and embedded video widget."""
        super().__init__(parent)
        self._aspect_ratio: float | None = None

        self._video_widget = QVideoWidget(self)
        self._video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.setStyleSheet("background-color: #111;")

    @property
    def video_widget(self) -> QVideoWidget:
        """Return the embedded Qt video widget."""
        return self._video_widget

    def set_aspect_ratio(self, width: int, height: int) -> None:
        """Remember native video dimensions for height-first scaling."""
        if width <= 0 or height <= 0:
            return
        self._aspect_ratio = width / height
        self._refit()

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802
        """Recompute video geometry when the panel is resized."""
        super().resizeEvent(event)
        self._refit()

    def _refit(self) -> None:
        """Scale video to fit panel height, then center horizontally."""
        container_width = self.width()
        container_height = self.height()
        if container_width <= 0 or container_height <= 0:
            return

        if self._aspect_ratio is None:
            self._video_widget.setGeometry(0, 0, container_width, container_height)
            return

        height = container_height
        width = int(height * self._aspect_ratio)
        if width > container_width:
            width = container_width
            height = int(width / self._aspect_ratio)

        x = (container_width - width) // 2
        y = (container_height - height) // 2
        self._video_widget.setGeometry(x, y, width, height)
