# Changelog

All notable RallyPin changes are recorded here.

## 1.0.0 - 2026-08-20

### Added

- Keyboard-first rally workflow with playback, seeking, speed, marking, tagging, undo, deletion, and export shortcuts.
- Mouse-accessible menus, buttons, timeline editing, tag filters, and adjustable video/list layout.
- RallyPin project files, automatic crash recovery, missing-video relinking, and unsaved-change prompts.
- Export progress, cancellation, tag-based export filtering, and collision-safe individual filenames.
- Automated core, UI smoke, project, and real FFmpeg integration tests.
- Python package metadata, Windows executable build configuration, and GitHub Actions workflows.

### Changed

- Rally boundaries now use accurate H.264/AAC encoding instead of keyframe-limited stream copying.
- Concatenated exports are staged and replace the destination only after a successful render.
- Segment validation and timeline undo behavior now live in the core layer.
- The UI uses a consistent dark theme and a dedicated segment table component.

### Fixed

- Ubuntu CI now installs the EGL runtime required to import PyQt6 during headless UI tests.
- The play-by-play export button now uses white text against its blue background.
- Invalid or negative segment ranges can no longer enter the timeline.
- Failed and cancelled exports clean up temporary output.
- Individual exports no longer overwrite existing clips without warning.
- Clearing a pending start now works even when no completed rally exists.
- Media controls stay disabled until Qt has actually loaded the selected video.
