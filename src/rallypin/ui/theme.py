"""Application-wide visual styling."""

APP_STYLESHEET = """
QMainWindow, QWidget {
    background: #111827;
    color: #e5e7eb;
    font-size: 13px;
}
QMenuBar, QMenu, QStatusBar {
    background: #172033;
    color: #e5e7eb;
}
QMenuBar::item:selected, QMenu::item:selected {
    background: #26344d;
}
QPushButton {
    background: #26344d;
    border: 1px solid #3b4b66;
    border-radius: 5px;
    min-height: 28px;
    padding: 2px 10px;
}
QPushButton:hover { background: #31415e; }
QPushButton:pressed { background: #1d4ed8; }
QPushButton:disabled { color: #6b7280; background: #1f2937; }
QPushButton#primaryButton {
    background: #2563eb;
    border-color: #3b82f6;
    font-weight: 600;
}
QPushButton#primaryButton:hover { background: #1d4ed8; }
QPushButton#playByPlayButton {
    background: #2563eb;
    border-color: #3b82f6;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#playByPlayButton:hover { background: #1d4ed8; }
QPushButton#playByPlayButton:disabled {
    background: #1f2937;
    border-color: #3b4b66;
    color: #6b7280;
}
QComboBox, QLineEdit {
    background: #0f172a;
    border: 1px solid #3b4b66;
    border-radius: 4px;
    min-height: 26px;
    padding: 1px 7px;
}
QComboBox:disabled, QLineEdit:disabled { color: #6b7280; }
QTableWidget {
    background: #0b1220;
    alternate-background-color: #101a2c;
    border: 1px solid #26344d;
    gridline-color: #26344d;
    selection-background-color: #1d4ed8;
    selection-color: white;
}
QHeaderView::section {
    background: #172033;
    border: 0;
    border-right: 1px solid #26344d;
    padding: 6px;
    font-weight: 600;
}
QSlider::groove:horizontal {
    background: #334155;
    height: 5px;
    border-radius: 2px;
}
QSlider::sub-page:horizontal { background: #3b82f6; }
QSlider::handle:horizontal {
    background: #f8fafc;
    border: 1px solid #94a3b8;
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QProgressBar {
    background: #0f172a;
    border: 1px solid #3b4b66;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk { background: #2563eb; }
QToolTip {
    background: #f8fafc;
    color: #111827;
    border: 1px solid #94a3b8;
}
"""
