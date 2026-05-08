# RallyPin

RallyPin is a local desktop tool for badminton video clipping.

This repository currently includes **Step 1** foundations:
- PyQt6 desktop app shell
- QtMultimedia video player
- Open/load local video
- Play/pause control
- Seek slider with time display
- Playback speed control

## Requirements

- Python 3.10+
- FFmpeg installed and available on your system `PATH`

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
      time_utils.py
      video_player_controller.py
    ui/
      main_window.py
```