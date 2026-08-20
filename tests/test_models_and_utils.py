from __future__ import annotations

import unittest

from rallypin.core.models import VideoSegment
from rallypin.core.tag_utils import parse_tags, sanitize_tag_for_filename
from rallypin.core.time_utils import format_milliseconds, parse_timestamp_to_milliseconds


class VideoSegmentTests(unittest.TestCase):
    def test_segment_validates_range_and_normalizes_tags(self) -> None:
        segment = VideoSegment(1_000, 2_500, (" Winner ", "winner", "Smash"))

        self.assertEqual(segment.duration_ms, 1_500)
        self.assertEqual(segment.tags, ("smash", "winner"))

    def test_segment_rejects_invalid_ranges(self) -> None:
        with self.assertRaises(ValueError):
            VideoSegment(-1, 100)
        with self.assertRaises(ValueError):
            VideoSegment(100, 100)
        with self.assertRaises(TypeError):
            VideoSegment(True, 100)


class UtilityTests(unittest.TestCase):
    def test_time_round_trip(self) -> None:
        value = 3_723_045
        self.assertEqual(parse_timestamp_to_milliseconds(format_milliseconds(value)), value)

    def test_time_parser_rejects_invalid_text(self) -> None:
        with self.assertRaises(ValueError):
            parse_timestamp_to_milliseconds("12:75:00.000")

    def test_tags_are_normalized_and_filename_safe(self) -> None:
        self.assertEqual(parse_tags(" Winner;  BACK court, winner "), ("back court", "winner"))
        self.assertEqual(sanitize_tag_for_filename('back/court: "left"'), "back_court_left")

    def test_tag_limits_are_enforced(self) -> None:
        with self.assertRaises(ValueError):
            parse_tags("x" * 41)
        with self.assertRaises(ValueError):
            parse_tags(",".join(f"tag{i}" for i in range(11)))


if __name__ == "__main__":
    unittest.main()
