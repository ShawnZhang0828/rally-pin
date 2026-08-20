"""Last-resort logging for unexpected GUI exceptions."""

from __future__ import annotations

import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QMessageBox


def install_exception_hook() -> None:
    """Install a GUI exception hook that also writes a local crash log."""

    def handle_exception(exception_type, exception, exception_traceback) -> None:  # noqa: ANN001
        if issubclass(exception_type, KeyboardInterrupt):
            sys.__excepthook__(exception_type, exception, exception_traceback)
            return

        details = "".join(
            traceback.format_exception(exception_type, exception, exception_traceback),
        )
        log_path = _write_crash_log(details)
        location = f"\n\nA diagnostic log was written to:\n{log_path}" if log_path else ""
        QMessageBox.critical(
            None,
            "RallyPin error",
            "RallyPin encountered an unexpected error. Your last timeline edit should be "
            f"available from recovery on the next launch.{location}",
        )

    sys.excepthook = handle_exception


def _write_crash_log(details: str) -> Path | None:
    """Append exception details to the per-user application data folder."""
    location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation,
    )
    if not location:
        return None
    log_path = Path(location) / "rallypin-crash.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"\n[{datetime.now(timezone.utc).isoformat()}]\n{details}\n")
    except OSError:
        return None
    return log_path
