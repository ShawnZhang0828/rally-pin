"""Application entrypoint for RallyPin."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from rallypin.ui.main_window import MainWindow


def run() -> int:
    """Create and run the RallyPin Qt application."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())

