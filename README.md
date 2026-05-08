# RallyPin

RallyPin is a local desktop tool for badminton video clipping.

This repository currently includes **Step 1** foundations:
- PyQt6 desktop app shell
- QtMultimedia video player
- Open/load local video
- Play/pause control
- Seek slider with time display
- Playback speed control

It now also includes **Step 2 and Step 3**:
- Rally tagging with keyboard shortcuts (`I` start, `O` end)
- Segment table with delete, clear, and double-click edit
- Background FFmpeg export worker (`QThread`) to keep UI responsive
- Export Mode A: concatenate rallies into one output
- Export Mode B: export each rally as `Play_###.mp4`

## Requirements

- Python 3.10+
- FFmpeg available either:
  - on your system `PATH`, or
  - via Python package `imageio-ffmpeg` (included in `requirements.txt`)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python run_rallypin.py
```

Alternative (if you want `-m` directly):

PowerShell:
```powershell
$env:PYTHONPATH = "src"
python -m rallypin.main
```

Command Prompt:
```bat
set PYTHONPATH=src
python -m rallypin.main
```

## Current Structure

```text
src/
  rallypin/
    main.py
    core/
      models.py
      segment_manager.py
      time_utils.py
      video_player_controller.py
      video_processing.py
    ui/
      export_worker.py
      main_window.py
```