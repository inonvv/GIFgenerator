#!/usr/bin/env python3
"""Modern GUI for GIFgenerator. Entry point for the bundled .exe."""

import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

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


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("GIF Generator")
        self.geometry("580x560")
        self.resizable(False, False)

        self.ffmpeg = vendor_path("ffmpeg.exe")
        self.ytdlp = vendor_path("yt-dlp.exe")
        if self.ytdlp:
            try_update_ytdlp_async(self.ytdlp)

        self._build_ui()
        self.last_outputs = None

    def _build_ui(self) -> None:
        ctk.CTkLabel(
            self, text="GIF Generator",
            font=ctk.CTkFont(size=26, weight="bold"),
        ).pack(pady=(24, 4))

        ctk.CTkLabel(
            self,
            text="Cut a slice of any online video into a GIF",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60"),
        ).pack(pady=(0, 18))

        form = ctk.CTkFrame(self, corner_radius=12)
        form.pack(padx=24, fill="x")

        self.url_var = ctk.StringVar()
        self.start_var = ctk.StringVar(value="0:00")
        self.duration_var = ctk.StringVar(value="4")
        self.name_var = ctk.StringVar()
        self.quality_var = ctk.StringVar(value="HD (720p, 24fps)")

        self._field(form, "YouTube URL", self.url_var, row=0, colspan=2, placeholder="https://www.youtube.com/watch?v=...")

        self._field(form, "Start", self.start_var, row=2, col=0, placeholder="e.g. 1:23")
        self._field(form, "Duration (seconds)", self.duration_var, row=2, col=1, placeholder="e.g. 4")

        self._field(form, "Name", self.name_var, row=4, colspan=2, placeholder="e.g. dog dancing")

        ctk.CTkLabel(form, text="Quality", font=ctk.CTkFont(size=12)).grid(
            row=6, column=0, sticky="w", padx=16, pady=(12, 0)
        )
        ctk.CTkOptionMenu(
            form,
            values=["Standard (480p, 15fps)", "HD (720p, 24fps)"],
            variable=self.quality_var,
            width=240,
        ).grid(row=7, column=0, columnspan=2, sticky="w", padx=16, pady=(2, 14))

        self.make_btn = ctk.CTkButton(
            self, text="Make GIF",
            height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            corner_radius=10,
            command=self.on_make_clicked,
        )
        self.make_btn.pack(pady=(20, 6), padx=24, fill="x")

        self.status = ctk.CTkLabel(self, text="Ready.", font=ctk.CTkFont(size=12))
        self.status.pack(pady=(8, 0))

        self.outputs_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=10),
            text_color=("gray35", "gray65"), justify="center",
        )
        self.outputs_label.pack(pady=(2, 0))

        self.open_btn = ctk.CTkButton(
            self, text="Open output folder",
            fg_color="transparent",
            border_width=1,
            corner_radius=10,
            state="disabled",
            command=self.open_output,
        )
        self.open_btn.pack(pady=(12, 20), padx=24, fill="x")

    def _field(self, parent, label, var, row, col=0, colspan=1, placeholder=""):
        ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=12)).grid(
            row=row, column=col, columnspan=colspan, sticky="w", padx=16, pady=(12, 0)
        )
        entry = ctk.CTkEntry(parent, textvariable=var, placeholder_text=placeholder, height=34)
        entry.grid(row=row + 1, column=col, columnspan=colspan, sticky="ew", padx=16, pady=(2, 0))
        parent.grid_columnconfigure(col, weight=1)
        return entry

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
            messagebox.showerror("Missing input", "Please enter a name.")
            return

        if "720" in self.quality_var.get():
            fps, width = 24, 720
        else:
            fps, width = 15, 480

        out_path = output_dir() / f"{sanitize_name(name)}.gif"
        self.make_btn.configure(state="disabled", text="Working…")
        self.open_btn.configure(state="disabled")
        self.outputs_label.configure(text="")
        self.status.configure(text="Starting…")
        threading.Thread(
            target=self._run_job,
            args=(url, start, duration, out_path, fps, width),
            daemon=True,
        ).start()

    def _run_job(self, url: str, start: str, duration: float, out_path: Path, fps: int, width: int) -> None:
        try:
            gif_path = make_gif(
                url=url, start=start, duration=duration, out=str(out_path),
                fps=fps, width=width,
                ffmpeg=self.ffmpeg, ytdlp=self.ytdlp,
                on_status=lambda s: self.after(0, self.status.configure, {"text": f"{s}…"}),
            )
        except subprocess.CalledProcessError as e:
            self.after(0, self._on_failure, f"yt-dlp/ffmpeg failed (exit {e.returncode}). Check the URL.")
            return
        except FileNotFoundError as e:
            self.after(0, self._on_failure, f"Required tool not found: {e}")
            return
        except Exception as e:
            self.after(0, self._on_failure, f"Unexpected error: {e}")
            return

        self.last_outputs = Path(gif_path)
        self.after(0, self._on_success)

    def _on_success(self) -> None:
        self.status.configure(text="Done.")
        self.outputs_label.configure(text=f"Saved: {self.last_outputs.name}")
        self.make_btn.configure(state="normal", text="Make GIF")
        self.open_btn.configure(state="normal")

    def _on_failure(self, msg: str) -> None:
        self.status.configure(text="Failed.")
        self.make_btn.configure(state="normal", text="Make GIF")
        messagebox.showerror("Failed", msg)

    def open_output(self) -> None:
        folder = self.last_outputs.parent if self.last_outputs else output_dir()
        try:
            os.startfile(folder)
        except AttributeError:
            subprocess.Popen(["xdg-open", str(folder)])


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
