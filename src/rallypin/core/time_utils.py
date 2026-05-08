"""Utilities for time conversion and formatting."""

from __future__ import annotations

import re


def format_milliseconds(milliseconds: int) -> str:
    """Convert milliseconds to `HH:MM:SS.mmm` format."""
    if milliseconds < 0:
        milliseconds = 0

    total_seconds: int = milliseconds // 1000
    ms: int = milliseconds % 1000
    seconds: int = total_seconds % 60
    minutes: int = (total_seconds // 60) % 60
    hours: int = total_seconds // 3600
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"


def parse_timestamp_to_milliseconds(value: str) -> int:
    """Parse `HH:MM:SS.mmm` text into milliseconds."""
    match = re.fullmatch(r"(\d{1,3}):([0-5]\d):([0-5]\d)\.(\d{3})", value.strip())
    if not match:
        raise ValueError("Timestamp must match HH:MM:SS.mmm")

    hours, minutes, seconds, milliseconds = (int(group) for group in match.groups())
    return (((hours * 60) + minutes) * 60 + seconds) * 1000 + milliseconds

