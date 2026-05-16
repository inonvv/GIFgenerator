#!/usr/bin/env python3
"""Tkinter GUI for GIFgenerator. Entry point for the bundled .exe."""

import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from gifgen import make_gif


def vendor_path(name: str):
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "vendor", name))
        candidates.append(os.path.join(meipass, name))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "vendor", name))
    candidates.append(os.path.join(here, name))
    for c in candidates:
        if os.path.exists(c):
            print(f"[vendor] found {name} at: {c}", flush=True)
            return c
    print(f"[vendor] NOT FOUND: {name} (searched: {candidates})", flush=True)
    return None


def output_dir() -> Path:
    home = Path(os.path.expanduser("~"))
    d = home / "Desktop" / "GIFGenerator"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sanitize_name(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s-]+", "_", name)
    return name or "clip"


def try_update_ytdlp_async(ytdlp: str) -> None:
    def run():
        try:
            subprocess.run(
                [ytdlp, "--update", "-q"],
                timeout=30,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    threading.Thread(target=run, daemon=True).start()


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("GIF Generator")
        root.geometry("520x320")
        root.resizable(False, False)

        self.ffmpeg = vendor_path("ffmpeg.exe")
        self.ytdlp = vendor_path("yt-dlp.exe")
        if self.ytdlp:
            try_update_ytdlp_async(self.ytdlp)

        frm = ttk.Frame(root, padding=16)
        frm.pack(fill="both", expand=True)

        self.url_var = tk.StringVar()
        self.start_var = tk.StringVar(value="0:00")
        self.duration_var = tk.StringVar(value="4")
        self.name_var = tk.StringVar()

        self._row(frm, 0, "YouTube URL:", self.url_var, width=50)
        self._row(frm, 1, "Start (e.g. 1:23):", self.start_var, width=20)
        self._row(frm, 2, "Duration (seconds):", self.duration_var, width=20)
        self._row(frm, 3, "Name:", self.name_var, width=30)

        self.make_btn = ttk.Button(frm, text="Make GIF", command=self.on_make_clicked)
        self.make_btn.grid(row=4, column=0, columnspan=2, pady=(16, 8), sticky="ew")

        self.status_var = tk.StringVar(value="ready.")
        ttk.Label(frm, textvariable=self.status_var, foreground="#555").grid(
            row=5, column=0, columnspan=2, sticky="w"
        )

        self.open_btn = ttk.Button(frm, text="Open output folder", command=self.open_output, state="disabled")
        self.open_btn.grid(row=6, column=0, columnspan=2, pady=(8, 0), sticky="ew")

        self.last_path = None

    def _row(self, parent, r, label, var, width=30):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=var, width=width).grid(row=r, column=1, sticky="w", pady=4)

    def on_make_clicked(self) -> None:
        url = self.url_var.get().strip()
        start = self.start_var.get().strip()
        duration_text = self.duration_var.get().strip()
        name = self.name_var.get().strip()

        if not url:
            messagebox.showerror("Missing input", "Please paste a YouTube URL.")
            return
        if not start:
            messagebox.showerror("Missing input", "Please enter a start time.")
            return
        try:
            duration = float(duration_text)
            if duration <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Bad duration", "Duration must be a positive number of seconds.")
            return
        if not name:
            messagebox.showerror("Missing input", "Please enter a name for the GIF.")
            return

        out_path = output_dir() / f"{sanitize_name(name)}.gif"
        self.make_btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        self.status_var.set("starting…")
        threading.Thread(
            target=self._run_job, args=(url, start, duration, out_path), daemon=True
        ).start()

    def _run_job(self, url: str, start: str, duration: float, out_path: Path) -> None:
        try:
            make_gif(
                url=url,
                start=start,
                duration=duration,
                out=str(out_path),
                ffmpeg=self.ffmpeg,
                ytdlp=self.ytdlp,
                on_status=lambda s: self.root.after(0, self.status_var.set, f"{s}…"),
            )
        except subprocess.CalledProcessError as e:
            self.root.after(0, self._on_failure, f"yt-dlp/ffmpeg failed (exit {e.returncode}). Check the URL.")
            return
        except FileNotFoundError as e:
            self.root.after(0, self._on_failure, f"Required tool not found: {e}")
            return
        except Exception as e:
            self.root.after(0, self._on_failure, f"Unexpected error: {e}")
            return

        self.last_path = out_path
        self.root.after(0, self._on_success, out_path)

    def _on_success(self, out_path: Path) -> None:
        self.status_var.set(f"done — {out_path.name}")
        self.make_btn.configure(state="normal")
        self.open_btn.configure(state="normal")

    def _on_failure(self, msg: str) -> None:
        self.status_var.set("failed.")
        self.make_btn.configure(state="normal")
        messagebox.showerror("Failed", msg)

    def open_output(self) -> None:
        folder = self.last_path.parent if self.last_path else output_dir()
        try:
            os.startfile(folder)
        except AttributeError:
            subprocess.Popen(["xdg-open", str(folder)])


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
