"""Domain models for RallyPin."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VideoSegment:
    """Represents a pinned rally segment in milliseconds."""

    start_ms: int
    end_ms: int
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject invalid time ranges and normalize tag storage."""
        if isinstance(self.start_ms, bool) or not isinstance(self.start_ms, int):
            raise TypeError("Segment start must be an integer number of milliseconds.")
        if isinstance(self.end_ms, bool) or not isinstance(self.end_ms, int):
            raise TypeError("Segment end must be an integer number of milliseconds.")
        if self.start_ms < 0:
            raise ValueError("Segment start cannot be negative.")
        if self.end_ms <= self.start_ms:
            raise ValueError("Segment end must be greater than start.")

        if not all(isinstance(tag, str) for tag in self.tags):
            raise TypeError("Segment tags must be strings.")
        normalized_tags = tuple(
            sorted({tag.strip().casefold() for tag in self.tags if tag.strip()})
        )
        object.__setattr__(self, "tags", normalized_tags)

    @property
    def duration_ms(self) -> int:
        """Return segment duration in milliseconds."""
        return self.end_ms - self.start_ms
