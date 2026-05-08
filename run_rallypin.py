"""Convenience launcher for RallyPin without PYTHONPATH setup."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    """Insert `src` into import path and start the app."""
    project_root = Path(__file__).resolve().parent
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    from rallypin.main import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())

