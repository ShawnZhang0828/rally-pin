from __future__ import annotations

import unittest

from rallypin.core.models import VideoSegment
from rallypin.core.segment_manager import SegmentManager


class SegmentManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SegmentManager()

    def test_capture_remove_and_undo(self) -> None:
        self.manager.pin_start(1_000)
        segment = self.manager.pin_end(2_000)

        self.assertEqual(segment, VideoSegment(1_000, 2_000))
        self.assertEqual(self.manager.segments, [segment])
        self.assertTrue(self.manager.remove_last())
        self.assertEqual(self.manager.segments, [])
        self.assertTrue(self.manager.undo())
        self.assertEqual(self.manager.segments, [segment])

    def test_pin_end_failure_preserves_pending_start(self) -> None:
        self.manager.pin_start(2_000)

        with self.assertRaises(ValueError):
            self.manager.pin_end(1_999)

        self.assertEqual(self.manager.pending_start_ms, 2_000)
        self.assertEqual(self.manager.segments, [])

    def test_delete_multiple_indices_and_undo(self) -> None:
        segments = [VideoSegment(0, 100), VideoSegment(200, 300), VideoSegment(400, 500)]
        self.manager.replace_all(segments)

        self.manager.remove_indices([0, 2, 2, 99])
        self.assertEqual(self.manager.segments, [segments[1]])
        self.assertTrue(self.manager.undo())
        self.assertEqual(self.manager.segments, segments)

    def test_tag_updates_are_undoable_and_unique(self) -> None:
        self.manager.replace_all([VideoSegment(0, 100), VideoSegment(200, 300)])

        self.manager.set_segment_tags(0, ("winner", "smash"))
        self.manager.set_segment_tags(1, ("winner",))

        self.assertEqual(self.manager.collect_unique_tags(), ["smash", "winner"])
        self.assertTrue(self.manager.undo())
        self.assertEqual(self.manager.segments[1].tags, ())

    def test_replacing_a_project_clears_undo_history(self) -> None:
        self.manager.pin_start(1_000)
        self.manager.replace_all([VideoSegment(10, 20)])

        self.assertFalse(self.manager.can_undo)
        self.assertIsNone(self.manager.pending_start_ms)


if __name__ == "__main__":
    unittest.main()
