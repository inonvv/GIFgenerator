#!/usr/bin/env python3
"""Cut a slice of an online video into both a GIF and an MP4."""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Optional, Tuple


def positive_float(value: str) -> float:
    n = float(value)
    if n <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return n


def positive_int(value: str) -> int:
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return n


def _ytdlp_cmd(ytdlp: Optional[str]) -> list:
    if ytdlp:
        return [ytdlp]
    return [sys.executable, "-m", "yt_dlp"]


def download_source(page_url: str, tmpdir: str, ytdlp: Optional[str] = None, ffmpeg: Optional[str] = None) -> str:
    out_template = os.path.join(tmpdir, "src.%(ext)s")
    cmd = _ytdlp_cmd(ytdlp) + [
        "-f", "bv*[ext=mp4][height<=720]/bv*[height<=720]/b",
        "--no-playlist",
        "--no-warnings",
        "-o", out_template,
    ]
    if ffmpeg:
        cmd += ["--ffmpeg-location", ffmpeg]
    cmd.append(page_url)
    subprocess.run(cmd, check=True)

    files = [f for f in os.listdir(tmpdir) if f.startswith("src.")]
    if not files:
        raise RuntimeError("yt-dlp produced no file")
    return os.path.join(tmpdir, files[0])


def to_gif(src: str, start: str, duration: float, out: str, fps: int, width: int, ffmpeg: Optional[str] = None) -> None:
    vf = (
        f"fps={fps},scale={width}:-1:flags=lanczos,"
        "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
    )
    cmd = [
        ffmpeg or "ffmpeg", "-y",
        "-ss", start,
        "-i", src,
        "-t", str(duration),
        "-vf", vf,
        "-loop", "0",
        out,
    ]
    subprocess.run(cmd, check=True)


def to_mp4(src: str, start: str, duration: float, out: str, fps: int, width: int, ffmpeg: Optional[str] = None) -> None:
    # -2 ensures even dimensions, required by libx264 yuv420p
    vf = f"fps={fps},scale={width}:-2:flags=lanczos"
    cmd = [
        ffmpeg or "ffmpeg", "-y",
        "-ss", start,
        "-i", src,
        "-t", str(duration),
        "-vf", vf,
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-crf", "23",
        "-an",
        out,
    ]
    subprocess.run(cmd, check=True)


def make_clip(
    url: str,
    start: str,
    duration: float,
    out: str,
    fps: int = 15,
    width: int = 480,
    ffmpeg: Optional[str] = None,
    ytdlp: Optional[str] = None,
    on_status: Optional[Callable[[str], None]] = None,
) -> Tuple[str, str]:
    def status(msg: str) -> None:
        if on_status:
            on_status(msg)

    base, ext = os.path.splitext(out)
    if ext.lower() != ".gif":
        base = out
    out_gif = base + ".gif"
    out_mp4 = base + ".mp4"

    status("downloading")
    with tempfile.TemporaryDirectory(prefix="gifgen_") as tmpdir:
        src = download_source(url, tmpdir, ytdlp=ytdlp, ffmpeg=ffmpeg)
        out_dir = os.path.dirname(os.path.abspath(out_gif))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        status("encoding mp4")
        to_mp4(src, start, duration, out_mp4, fps, width, ffmpeg=ffmpeg)
        # Encode GIF from the clean small MP4 we just produced — avoids re-seeking the
        # full source and dodges AV1 decoder + palettegen memory blow-up on long videos.
        status("encoding gif")
        to_gif(out_mp4, "0", duration, out_gif, fps, width, ffmpeg=ffmpeg)
    status("done")
    return out_gif, out_mp4


def make_gif(*args, **kwargs):
    return make_clip(*args, **kwargs)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Make a GIF and MP4 from a slice of an online video (YouTube, Twitch, Vimeo, etc.).",
    )
    parser.add_argument("url", help="Video page URL (anything yt-dlp supports)")
    parser.add_argument("--start", required=True, help="Start timestamp (e.g. 1:23, 0:01:23, or seconds)")
    parser.add_argument("--duration", required=True, type=positive_float, help="Clip duration in seconds")
    parser.add_argument("--out", default="out.gif", help="Output base path (default: out.gif). Produces both .gif and .mp4 next to each other.")
    parser.add_argument("--fps", default=15, type=positive_int, help="Frame rate (default: 15)")
    parser.add_argument("--width", default=480, type=positive_int, help="Width in pixels, height auto (default: 480)")
    parser.add_argument("--ffmpeg", default=None, help="Path to ffmpeg binary (defaults to PATH)")
    parser.add_argument("--ytdlp", default=None, help="Path to yt-dlp binary (defaults to python -m yt_dlp)")
    args = parser.parse_args()

    ffmpeg = args.ffmpeg or shutil.which("ffmpeg")
    if ffmpeg is None:
        sys.exit("error: ffmpeg not found on PATH. Install ffmpeg first.")

    try:
        gif_path, mp4_path = make_clip(
            args.url, args.start, args.duration, args.out,
            fps=args.fps, width=args.width,
            ffmpeg=ffmpeg, ytdlp=args.ytdlp,
            on_status=lambda s: print(s, file=sys.stderr),
        )
    except FileNotFoundError as e:
        sys.exit(f"error: required binary not found: {e}")
    except subprocess.CalledProcessError as e:
        sys.exit(f"error: subprocess failed with exit code {e.returncode}")
    except RuntimeError as e:
        sys.exit(f"error: {e}")

    print(f"done:\n  gif: {gif_path}\n  mp4: {mp4_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
