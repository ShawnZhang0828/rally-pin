"""Segment capture and validation logic."""

from __future__ import annotations

from rallypin.core.models import VideoSegment


class SegmentManager:
    """Maintains ordered rally segments and active pin state."""

    def __init__(self) -> None:
        """Initialize an empty segment manager."""
        self._segments: list[VideoSegment] = []
        self._pending_start_ms: int | None = None

    @property
    def segments(self) -> list[VideoSegment]:
        """Return a shallow copy of all segments."""
        return list(self._segments)

    @property
    def pending_start_ms(self) -> int | None:
        """Return currently pinned start time if one exists."""
        return self._pending_start_ms

    def clear(self) -> None:
        """Clear all segment data and pending state."""
        self._segments.clear()
        self._pending_start_ms = None

    def pin_start(self, timestamp_ms: int) -> None:
        """Record start time for the next segment."""
        self._pending_start_ms = max(0, timestamp_ms)

    def pin_end(self, timestamp_ms: int) -> VideoSegment:
        """Finalize a segment from pending start and end timestamps."""
        if self._pending_start_ms is None:
            raise ValueError("Pin Start is required before Pin End.")

        end_ms = max(0, timestamp_ms)
        start_ms = self._pending_start_ms
        if end_ms <= start_ms:
            raise ValueError("Pin End must be greater than Pin Start.")

        segment = VideoSegment(start_ms=start_ms, end_ms=end_ms)
        self._segments.append(segment)
        self._pending_start_ms = None
        return segment

    def remove_indices(self, indices: list[int]) -> None:
        """Delete one or more segments by zero-based indices."""
        for index in sorted(set(indices), reverse=True):
            if 0 <= index < len(self._segments):
                del self._segments[index]

    def replace_segment(self, index: int, segment: VideoSegment) -> None:
        """Replace a segment row after edit validation."""
        if index < 0 or index >= len(self._segments):
            raise IndexError("Segment index out of range.")
        if segment.end_ms <= segment.start_ms:
            raise ValueError("Segment end must be greater than start.")
        self._segments[index] = segment

