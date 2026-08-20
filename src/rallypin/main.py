"""Application entrypoint for RallyPin."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from rallypin import __version__
from rallypin.error_handler import install_exception_hook
from rallypin.ui.main_window import MainWindow
from rallypin.ui.theme import APP_STYLESHEET


def run() -> int:
    """Create and run the RallyPin Qt application."""
    app = QApplication(sys.argv)
    app.setOrganizationName("RallyPin")
    app.setApplicationName("RallyPin")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    install_exception_hook()
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
