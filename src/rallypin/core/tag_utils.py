"""Parsing and normalization for clip tags."""

from __future__ import annotations

import re

MAX_TAGS = 10
MAX_TAG_LENGTH = 40


def parse_tags(text: str) -> tuple[str, ...]:
    """Parse user-facing tag text into a sorted unique tuple.

    Accepts comma- or semicolon-separated tokens. Empty tokens are dropped.
    """
    raw_parts = re.split(r"[,;]", text)
    tags = {re.sub(r"\s+", " ", part.strip()).casefold() for part in raw_parts if part.strip()}
    if len(tags) > MAX_TAGS:
        raise ValueError(f"A clip can have at most {MAX_TAGS} tags.")
    too_long = next((tag for tag in tags if len(tag) > MAX_TAG_LENGTH), None)
    if too_long is not None:
        raise ValueError(f"Tags can be at most {MAX_TAG_LENGTH} characters long.")
    return tuple(sorted(tags))


def tags_to_display(tags: tuple[str, ...]) -> str:
    """Render tags as comma-separated text for display and editing."""
    return ", ".join(tags)


def sanitize_tag_for_filename(tag: str) -> str:
    """Return a filesystem-safe fragment from a single tag."""
    cleaned = re.sub(r'[<>:"/\\|?*\s]+', "_", tag.strip())
    cleaned = cleaned.strip("_.")[:32].rstrip("_.")
    return cleaned or "tag"
