"""Keyboard shortcut reference used by the help dialog."""

from __future__ import annotations

SHORTCUT_GROUPS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Playback",
        (
            ("Space or K", "Play or pause"),
            ("Left / Right", "Seek 2 seconds"),
            ("Shift+Left / Shift+Right", "Seek 10 seconds"),
            ("[ / ]", "Decrease or increase playback speed"),
            ("M", "Mute or unmute"),
        ),
    ),
    (
        "Rally marking",
        (
            ("I", "Pin rally start"),
            ("O", "Pin rally end"),
            ("N", "Edit tags for the selected rally"),
            ("E", "Edit timing for the selected rally"),
            ("Enter", "Jump to the selected rally"),
            ("Delete", "Delete selected rallies"),
            ("Ctrl+Z", "Undo the last timeline change"),
            ("Ctrl+Shift+Delete", "Clear the timeline"),
            ("Escape", "Cancel a pending start"),
        ),
    ),
    (
        "Files and export",
        (
            ("Ctrl+O", "Open video"),
            ("Ctrl+Shift+O", "Open RallyPin project"),
            ("Ctrl+S", "Save project"),
            ("Ctrl+Shift+S", "Save project as"),
            ("Ctrl+F", "Choose an export filter"),
            ("Ctrl+E", "Export one play-by-play video"),
            ("Ctrl+Shift+E", "Export individual clips"),
            ("F1", "Show this shortcut list"),
        ),
    ),
)


def shortcut_help_html() -> str:
    """Return a compact HTML shortcut reference."""
    sections: list[str] = []
    for title, shortcuts in SHORTCUT_GROUPS:
        rows = "".join(
            f"<tr><td><b>{keys}</b></td><td>{description}</td></tr>"
            for keys, description in shortcuts
        )
        sections.append(
            f"<h3>{title}</h3><table cellspacing='5' cellpadding='2'>{rows}</table>",
        )
    return "".join(sections)
