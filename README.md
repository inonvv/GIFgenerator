# GIF Generator

Make a GIF from a slice of an online video. YouTube, Twitch, Vimeo, Twitter — anything yt-dlp supports.

## For non-coders: download and run (Windows)

You don't need Python, the command line, or any installation. Just one file.

### Step 1 — Download the app

1. Click the [**Releases**](../../releases/latest) link.
2. Under the latest release you'll see a file called **`GIFGenerator.exe`**. Click it to download.
3. Wait for it to finish (~100 MB).

> Where did it go? Probably your `Downloads` folder. You can move it to your Desktop or anywhere you like.

### Step 2 — Open the app

1. **Double-click `GIFGenerator.exe`** in File Explorer.
2. The first time you run it, Windows may show a blue screen titled **"Windows protected your PC"**. This is normal — Windows shows it for any app that hasn't paid for a code-signing certificate. It does **not** mean the app is unsafe.
   - Click the small text **"More info"**.
   - A new button appears: **"Run anyway"**. Click it.
3. After a few seconds, a small window opens. You only have to do the "Run anyway" step **once**.

> Still blocked? Right-click `GIFGenerator.exe` → **Properties** → at the bottom check **"Unblock"** → click **OK**. Then double-click again.

### Step 3 — Make a GIF

In the window, fill in the four fields:

| Field | What to put | Example |
|---|---|---|
| **YouTube URL** | The full link to the video | `https://www.youtube.com/watch?v=...` |
| **Start** | Where the GIF should begin | `1:23` (1 minute 23 seconds) |
| **Duration (seconds)** | How long the GIF should be | `4` |
| **Name** | A short name for the file | `dog dancing` |

Click **Make GIF**. Wait 10–60 seconds. When the status says **"done"**, click **Open output folder** to find your GIF.

### Step 4 — Where is the GIF?

All your GIFs are saved to: **`Desktop\GIFGenerator\<name>.gif`**

### Step 5 — Send it

- **Email** works perfectly: just attach the `.gif` file. Recipients see it animated.
- **Telegram, Discord, Signal**: drag the file in. Plays automatically.
- **WhatsApp** is finicky — it sometimes shows GIFs as a still photo of the first frame. Workarounds: use WhatsApp Web and attach as **Document** (paperclip icon → Document), or just send via email.

### Troubleshooting

- **"Could not find file" / weird error window** — close the app, re-open it, try a different YouTube URL first to see if the issue is the URL or the app.
- **"Make GIF" button does nothing** — check the status text at the bottom of the window. If it stays on "downloading…" for over 2 minutes, your internet might be slow or the video might be unusually long.
- **Need a different start time format** — `1:23` works, `0:01:23` works, raw seconds (`83`) also works.

> The app is open source — every line of code is in this repo. No tracking, no ads, no account needed.

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
