# RallyPin

RallyPin cuts the waiting time out of badminton recordings. Mark each rally while the video plays, then export the marked rallies as one play-by-play video or as separate clips.

The main editing loop works from the keyboard: `I` marks the start of a rally, `O` marks the end, and the arrow keys move through the recording. Every command also has a button or menu item. RallyPin processes the video locally and does not upload it.

## 中文快速上手

RallyPin 用来快速剪掉羽毛球视频中捡球、走位和准备发球的部分。打开视频后，用 `I` 标记每个回合的开始，用 `O` 标记结束，最后按 `Ctrl+E` 导出完整的 play-by-play 视频。项目文件会保存所有时间点和标签，程序意外退出时也会保留一份恢复记录。

## Install

### Windows app

Download `RallyPin.exe` from the [latest GitHub release](../../releases/latest) and run it. The automated Windows build is not code signed, so Windows may show a SmartScreen warning on first launch.

### Run from source

RallyPin requires Python 3.10 or newer.

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install .
rallypin
```

On macOS or Linux, activate the environment with `source .venv/bin/activate`. You can also start the repository checkout with `python run_rallypin.py` or `python -m rallypin` after installation.

The `imageio-ffmpeg` dependency includes FFmpeg, so a separate system install is normally unnecessary.

## Edit a match

1. Open a video with `Ctrl+O`.
2. Press `Space` to play or pause. Use `Left` and `Right` to seek by two seconds, or hold `Shift` to seek by ten seconds.
3. Press `I` when a rally starts and `O` when it ends. The completed rally appears in the table.
4. Select a rally and press `N` to add tags such as `winner`, `smash`, or `long rally`. Double-click its start or end time if it needs a precise correction.
5. Save the timeline with `Ctrl+S`. RallyPin project files use the `.rallypin.json` extension and do not contain a copy of the video.
6. Choose all rallies, untagged rallies, or one tag from the export filter.
7. Press `Ctrl+E` to make one play-by-play MP4. Use `Ctrl+Shift+E` to export separate clips.

RallyPin encodes exports as H.264 video with AAC audio. This makes the marked boundaries accurate instead of snapping them to nearby video keyframes. Encoding takes longer than a rough stream-copy cut, but it runs in the background and can be cancelled.

## Keyboard shortcuts

| Keys | Action |
| --- | --- |
| `Space` or `K` | Play or pause |
| `Left` / `Right` | Seek backward or forward 2 seconds |
| `Shift+Left` / `Shift+Right` | Seek backward or forward 10 seconds |
| `[` / `]` | Decrease or increase playback speed |
| `M` | Mute or unmute |
| `I` | Pin rally start |
| `O` | Pin rally end |
| `Escape` | Cancel a pending start |
| `N` | Edit tags for the selected rally |
| `E` | Edit timing for the selected rally |
| `Enter` | Jump to the selected rally |
| `Delete` | Delete selected rallies |
| `Backspace` | Remove the last rally |
| `Ctrl+Z` | Undo the last timeline change |
| `Ctrl+Shift+Delete` | Clear the timeline |
| `Ctrl+O` | Open a video |
| `Ctrl+Shift+O` | Open a RallyPin project |
| `Ctrl+S` | Save the project |
| `Ctrl+Shift+S` | Save the project under a new name |
| `Ctrl+F` | Choose an export filter |
| `Ctrl+E` | Export one play-by-play video |
| `Ctrl+Shift+E` | Export individual clips |
| `F1` | Show shortcuts in the app |

## Projects and recovery

A project stores the source video path, rally times, and tags. Relative video paths are used when possible, which makes it easier to move a project and its video together. If the video has moved, RallyPin asks you to locate it.

After every timeline edit, RallyPin writes a recovery copy in the current user's application data folder. A clean project save removes that copy. If the app closes unexpectedly, the next launch offers to restore the unsaved timeline.

## Export behavior

- A play-by-play export is written to a temporary location first. RallyPin replaces the chosen destination only after FFmpeg finishes successfully.
- Individual clips use names such as `Play_001_winner_smash.mp4`. Existing clips are kept; a number is added to the new filename when needed.
- The tag filter changes which rallies are exported without changing the saved timeline.
- Cancelling an export stops the active FFmpeg process and removes unfinished temporary files. Individual clips that finished before cancellation remain in the chosen folder.

## Supported input

The file picker accepts MP4, MOV, MKV, AVI, M4V, and WebM files. Actual playback support depends on the codecs available to Qt on the operating system. H.264 video with AAC audio in an MP4 container is the most portable choice.

If a video does not open, convert it to H.264/AAC MP4 and try again. If export fails, check that the destination has enough free space and that the current user can write to it.

## Development

Install the development tools and run the checks:

```powershell
python -m pip install -e ".[dev]"
python -m ruff check .
python -m unittest discover -s tests -v
python -m compileall -q src run_rallypin.py
```

The test suite covers segment validation, undo behavior, project round trips, tag editing, window construction, cancellation, and a real FFmpeg cut-and-concatenate run.

Build the Windows executable with:

```powershell
.\scripts\build_windows.ps1
```

The result is written to `dist\RallyPin.exe`. GitHub Actions runs the same tests on Windows and Linux. Publishing a GitHub release builds the Windows executable and attaches it to the release.

## Repository layout

```text
src/rallypin/
  core/        Timeline, project, playback, and FFmpeg logic
  ui/          Qt window, segment table, theme, and export worker
tests/         Unit, UI smoke, and FFmpeg integration tests
scripts/       Local build scripts
.github/       Continuous integration and release build workflows
```

## License

This repository does not currently include a license. Add the license you want before inviting outside contributions.
