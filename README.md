# GIF Generator

Make a GIF from a slice of an online video. YouTube, Twitch, Vimeo, Twitter — anything yt-dlp supports.

## For most people: download the app

1. Go to the [Releases page](../../releases/latest) and download **`GIFGenerator.exe`**.
2. Double-click it.
3. **If Windows shows a blue "Windows protected your PC" screen:** click **More info** → **Run anyway**. (Windows shows this for any app that isn't code-signed. The app is open source — you can read every line in this repo.)
4. Paste a YouTube URL, set the start time (e.g. `1:23`), duration in seconds (e.g. `4`), and a name. Click **Make GIF**. The GIF lands in `Desktop\GIFGenerator\`.

No Python, no ffmpeg install, no command line — everything is bundled inside the .exe.

> Sending the GIF? Email works perfectly. WhatsApp sometimes shows it as a static first frame — drag it into WhatsApp Web as a Document, or send as the produced file via email/Telegram which display animated GIFs natively.

## For developers / CLI users

### Prerequisites

- Python 3.9+
- `ffmpeg` on PATH (`winget install ffmpeg` on Windows, `brew install ffmpeg` on macOS, `apt install ffmpeg` on Linux).

### Install

```bash
pip install -r requirements.txt
```

### Usage

```bash
python gifgen.py <url> --start <timestamp> --duration <seconds> [--out file.gif] [--fps 15] [--width 480]
```

#### Examples

```bash
# 4-second GIF starting at 1:23
python gifgen.py "https://youtu.be/dQw4w9WgXcQ" --start 1:23 --duration 4 --out clip.gif

# Smaller, lower-fps GIF
python gifgen.py "https://youtu.be/dQw4w9WgXcQ" --start 0:30 --duration 3 --fps 10 --width 320

# Higher quality
python gifgen.py "https://youtu.be/dQw4w9WgXcQ" --start 0:30 --duration 3 --fps 24 --width 720
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--start` | (required) | Start timestamp. `MM:SS`, `HH:MM:SS`, or raw seconds. |
| `--duration` | (required) | Clip length in seconds. |
| `--out` | `out.gif` | Output file path. |
| `--fps` | `15` | GIF frame rate. |
| `--width` | `480` | Output width in pixels. Height is auto-scaled. |

### Run the GUI from source

```bash
python app.py
```

## How it works

1. `yt-dlp` downloads the **lowest-resolution video-only stream** (capped at 360p, no audio — GIFs are silent) to a temp file. For a typical short clip this is 1–5 MB.
2. `ffmpeg -ss <start> -i <tmpfile> -t <duration> -vf "<palette filter>" out.gif` seeks into the local file, cuts the segment, and encodes a high-quality GIF.
3. Temp file is deleted automatically.

The GIF filter uses the standard two-pass palette technique (`palettegen` + `paletteuse`) for clean colors.

This approach is more reliable than streaming directly from YouTube — YouTube's DASH-fragmented format breaks ffmpeg's HTTP input-seek and partial-section downloads. A small temp download + local cut is fast and predictable.

## Building the .exe yourself

```bash
pip install -r requirements-dev.txt
# Put ffmpeg.exe and yt-dlp.exe into ./vendor/
pyinstaller --clean gifgen.spec
# Result: dist/GIFGenerator.exe
```

Or just push a tag like `v0.1.0` — `.github/workflows/release.yml` builds and publishes the .exe to GitHub Releases automatically.
