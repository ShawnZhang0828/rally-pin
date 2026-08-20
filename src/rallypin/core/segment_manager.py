"""Segment capture and validation logic."""

from __future__ import annotations

from rallypin.core.models import VideoSegment


class SegmentManager:
    """Maintains ordered rally segments and active pin state."""

    MAX_UNDO_STATES = 100

    def __init__(self) -> None:
        """Initialize an empty segment manager."""
        self._segments: list[VideoSegment] = []
        self._pending_start_ms: int | None = None
        self._undo_stack: list[tuple[list[VideoSegment], int | None]] = []

    @property
    def segments(self) -> list[VideoSegment]:
        """Return a shallow copy of all segments."""
        return list(self._segments)

    @property
    def pending_start_ms(self) -> int | None:
        """Return currently pinned start time if one exists."""
        return self._pending_start_ms

    @property
    def can_undo(self) -> bool:
        """Return whether a previous timeline state is available."""
        return bool(self._undo_stack)

    def clear(self) -> None:
        """Clear all segment data and pending state."""
        if not self._segments and self._pending_start_ms is None:
            return
        self._remember_state()
        self._segments.clear()
        self._pending_start_ms = None

    def replace_all(self, segments: list[VideoSegment]) -> None:
        """Replace the current timeline with validated project segments."""
        self._segments = list(segments)
        self._pending_start_ms = None
        self._undo_stack.clear()

    def cancel_pending(self) -> bool:
        """Cancel a pinned start and report whether one existed."""
        if self._pending_start_ms is None:
            return False
        self._remember_state()
        self._pending_start_ms = None
        return True

    def undo(self) -> bool:
        """Restore the timeline state before the most recent change."""
        if not self._undo_stack:
            return False
        segments, pending_start_ms = self._undo_stack.pop()
        self._segments = segments
        self._pending_start_ms = pending_start_ms
        return True

    def pin_start(self, timestamp_ms: int) -> None:
        """Record start time for the next segment."""
        self._remember_state()
        self._pending_start_ms = max(0, timestamp_ms)

    def pin_end(self, timestamp_ms: int) -> VideoSegment:
        """Finalize a segment from pending start and end timestamps."""
        if self._pending_start_ms is None:
            raise ValueError("Pin Start is required before Pin End.")

        end_ms = max(0, timestamp_ms)
        start_ms = self._pending_start_ms
        if end_ms <= start_ms:
            raise ValueError("Pin End must be greater than Pin Start.")

        self._remember_state()
        segment = VideoSegment(start_ms=start_ms, end_ms=end_ms)
        self._segments.append(segment)
        self._pending_start_ms = None
        return segment

    def remove_indices(self, indices: list[int]) -> None:
        """Delete one or more segments by zero-based indices."""
        valid_indices = sorted(
            {index for index in indices if 0 <= index < len(self._segments)},
            reverse=True,
        )
        if not valid_indices:
            return
        self._remember_state()
        for index in valid_indices:
            del self._segments[index]

    def remove_last(self) -> bool:
        """Remove the most recently added segment, if any."""
        if not self._segments:
            return False
        self._remember_state()
        self._segments.pop()
        return True

    def replace_segment(self, index: int, segment: VideoSegment) -> None:
        """Replace a segment row after edit validation."""
        if index < 0 or index >= len(self._segments):
            raise IndexError("Segment index out of range.")
        self._remember_state()
        self._segments[index] = segment

    def set_segment_tags(self, index: int, tags: tuple[str, ...]) -> None:
        """Update only the tag set for an existing segment."""
        if index < 0 or index >= len(self._segments):
            raise IndexError("Segment index out of range.")
        current = self._segments[index]
        updated = VideoSegment(
            start_ms=current.start_ms,
            end_ms=current.end_ms,
            tags=tags,
        )
        if updated == current:
            return
        self._remember_state()
        self._segments[index] = updated

    def collect_unique_tags(self) -> list[str]:
        """Return sorted unique tags across all segments."""
        collected: set[str] = set()
        for segment in self._segments:
            collected.update(segment.tags)
        return sorted(collected)

    def _remember_state(self) -> None:
        """Store a bounded copy of the current state for one-step undo actions."""
        self._undo_stack.append((list(self._segments), self._pending_start_ms))
        if len(self._undo_stack) > self.MAX_UNDO_STATES:
            del self._undo_stack[0]
