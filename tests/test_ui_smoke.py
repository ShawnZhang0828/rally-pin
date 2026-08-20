from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from rallypin.core.models import VideoSegment  # noqa: E402
from rallypin.ui.main_window import MainWindow  # noqa: E402
from rallypin.ui.segment_table import SegmentTable  # noqa: E402


class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setOrganizationName("RallyPinTests")
        cls.app.setApplicationName("RallyPinTests")

    def test_main_window_constructs_with_safe_initial_state(self) -> None:
        window = MainWindow()

        self.assertEqual(window.windowTitle(), "No video - RallyPin")
        self.assertFalse(window._play_pause_button.isEnabled())
        self.assertFalse(window._export_concat_button.isEnabled())
        self.assertEqual(window._segments_table.rowCount(), 0)

        window._settings.clear()
        window.close()

    def test_segment_table_normalizes_and_rejects_tag_edits(self) -> None:
        table = SegmentTable()
        table.render([VideoSegment(0, 1_000, ("winner",))])
        emitted: list[tuple[int, tuple[str, ...]]] = []
        errors: list[str] = []
        table.tags_changed.connect(lambda row, tags: emitted.append((row, tags)))
        table.tag_validation_failed.connect(errors.append)

        table.item(0, 4).setText(" Smash, smash ")
        self.assertEqual(table.item(0, 4).text(), "smash")
        self.assertEqual(emitted[-1], (0, ("smash",)))

        table.item(0, 4).setText("x" * 41)
        self.assertEqual(table.item(0, 4).text(), "smash")
        self.assertTrue(errors)

    def test_text_editor_temporarily_releases_timeline_shortcuts(self) -> None:
        window = MainWindow()
        window._segment_manager.replace_all([VideoSegment(0, 1_000)])
        window._segment_manager.set_segment_tags(0, ("winner",))
        window._refresh_segments_table()
        window._segments_table.editing_state_changed.emit(True)

        self.assertFalse(window._undo_action.isEnabled())
        self.assertFalse(window._shortcut_edit_tags.isEnabled())

        window._settings.clear()
        window.close()


if __name__ == "__main__":
    unittest.main()
