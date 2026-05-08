"""Domain models for RallyPin."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class VideoSegment:
    """Represents a pinned rally segment in milliseconds."""

    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        """Return segment duration in milliseconds."""
        return max(0, self.end_ms - self.start_ms)

