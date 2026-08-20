"""Segment table widget with isolated rendering and tag editing behavior."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
)

from rallypin.core.models import VideoSegment
from rallypin.core.tag_utils import parse_tags, tags_to_display
from rallypin.core.time_utils import format_milliseconds


class SegmentTable(QTableWidget):
    """Display rally segments and emit normalized tag edits."""

    tags_changed = pyqtSignal(int, tuple)
    tag_validation_failed = pyqtSignal(str)
    editing_state_changed = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        """Configure columns, selection, and edit behavior."""
        super().__init__(parent)
        self._segments: list[VideoSegment] = []
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(("Play", "Start", "End", "Duration", "Tags"))
        header = self.horizontalHeader()
        for column in range(4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed,
        )
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(False)
        self.verticalHeader().setVisible(False)
        self._tag_delegate = _TagEditorDelegate(self)
        self.setItemDelegateForColumn(4, self._tag_delegate)
        self._tag_delegate.editing_state_changed.connect(self.editing_state_changed.emit)
        self.itemChanged.connect(self._on_item_changed)

    def render(self, segments: list[VideoSegment]) -> None:
        """Replace all displayed rows while suppressing edit signals."""
        self._segments = list(segments)
        self.blockSignals(True)
        self.setRowCount(len(segments))
        editable = (
            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        )
        read_only = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        for row, segment in enumerate(segments):
            values = (
                str(row + 1),
                format_milliseconds(segment.start_ms),
                format_milliseconds(segment.end_ms),
                format_milliseconds(segment.duration_ms),
                tags_to_display(segment.tags),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(editable if column == 4 else read_only)
                if column in (0, 1, 2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(row, column, item)
        self.blockSignals(False)

    def selected_rows(self) -> list[int]:
        """Return sorted, unique selected row indices."""
        return sorted({index.row() for index in self.selectedIndexes()})

    def selected_or_last_row(self) -> int | None:
        """Return the last selected row, or the final row when none is selected."""
        selected = self.selected_rows()
        if selected:
            return selected[-1]
        if self.rowCount() > 0:
            return self.rowCount() - 1
        return None

    def begin_tag_edit(self, row: int | None = None) -> None:
        """Start inline tag editing for a selected or explicit row."""
        if row is None:
            row = self.selected_or_last_row()
        if row is None or not 0 <= row < self.rowCount():
            return
        item = self.item(row, 4)
        if item is None:
            return
        self.selectRow(row)
        self.setCurrentCell(row, 4)
        self.editItem(item)

    def select_last(self) -> None:
        """Select and reveal the final row."""
        if self.rowCount() == 0:
            return
        row = self.rowCount() - 1
        self.selectRow(row)
        self.scrollToItem(self.item(row, 0))

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Validate the editable tags column and emit normalized tags."""
        if item.column() != 4:
            return
        row = item.row()
        if not 0 <= row < len(self._segments):
            return
        try:
            tags = parse_tags(item.text())
        except ValueError as exc:
            self.blockSignals(True)
            item.setText(tags_to_display(self._segments[row].tags))
            self.blockSignals(False)
            self.tag_validation_failed.emit(str(exc))
            return

        normalized_display = tags_to_display(tags)
        if item.text() != normalized_display:
            self.blockSignals(True)
            item.setText(normalized_display)
            self.blockSignals(False)
        current = self._segments[row]
        self._segments[row] = VideoSegment(
            start_ms=current.start_ms,
            end_ms=current.end_ms,
            tags=tags,
        )
        self.tags_changed.emit(row, tags)


class _TagEditorDelegate(QStyledItemDelegate):
    """Report the lifetime of the inline tag editor to the main window."""

    editing_state_changed = pyqtSignal(bool)

    def createEditor(self, parent, option, index):  # noqa: ANN001, N802
        editor = super().createEditor(parent, option, index)
        self.editing_state_changed.emit(True)
        return editor

    def destroyEditor(self, editor, index) -> None:  # noqa: ANN001, N802
        self.editing_state_changed.emit(False)
        super().destroyEditor(editor, index)
