#!/usr/bin/env python3
"""Create a GIF from a slice of an online video by downloading a low-res copy then cutting locally."""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Optional


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


def download_low_res(page_url: str, tmpdir: str, ytdlp: Optional[str] = None, ffmpeg: Optional[str] = None) -> str:
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


def make_gif(
    url: str,
    start: str,
    duration: float,
    out: str,
    fps: int = 15,
    width: int = 480,
    ffmpeg: Optional[str] = None,
    ytdlp: Optional[str] = None,
    on_status: Optional[Callable[[str], None]] = None,
) -> None:
    def status(msg: str) -> None:
        if on_status:
            on_status(msg)

    status("downloading")
    with tempfile.TemporaryDirectory(prefix="gifgen_") as tmpdir:
        src = download_low_res(url, tmpdir, ytdlp=ytdlp, ffmpeg=ffmpeg)
        status("encoding")
        out_dir = os.path.dirname(os.path.abspath(out))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        to_gif(src, start, duration, out, fps, width, ffmpeg=ffmpeg)
    status("done")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Make a GIF from a slice of an online video (YouTube, Twitch, Vimeo, etc.). Downloads a low-res copy to temp then cuts locally.",
    )
    parser.add_argument("url", help="Video page URL (anything yt-dlp supports)")
    parser.add_argument("--start", required=True, help="Start timestamp (e.g. 1:23, 0:01:23, or seconds)")
    parser.add_argument("--duration", required=True, type=positive_float, help="Clip duration in seconds")
    parser.add_argument("--out", default="out.gif", help="Output GIF path (default: out.gif)")
    parser.add_argument("--fps", default=15, type=positive_int, help="GIF frame rate (default: 15)")
    parser.add_argument("--width", default=480, type=positive_int, help="GIF width in pixels, height auto (default: 480)")
    parser.add_argument("--ffmpeg", default=None, help="Path to ffmpeg binary (defaults to PATH)")
    parser.add_argument("--ytdlp", default=None, help="Path to yt-dlp binary (defaults to python -m yt_dlp)")
    args = parser.parse_args()

    ffmpeg = args.ffmpeg or shutil.which("ffmpeg")
    if ffmpeg is None:
        sys.exit("error: ffmpeg not found on PATH. Install ffmpeg first.")

    try:
        make_gif(
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

    print(f"done: {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
