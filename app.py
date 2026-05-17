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
import qrcode
from PIL import Image

from gifgen import make_gif
from share_server import ShareSession, serve_file


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


_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def try_update_ytdlp_async(ytdlp: str) -> None:
    def run():
        try:
            subprocess.run(
                [ytdlp, "--update", "-q"],
                timeout=30,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_NO_WINDOW,
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
        self.geometry("580x680")
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

        self.progress = ctk.CTkProgressBar(self, mode="indeterminate", height=6)
        self.progress.pack(pady=(8, 0), padx=24, fill="x")
        self.progress.set(0)

        self.status = ctk.CTkLabel(self, text="Ready.", font=ctk.CTkFont(size=12))
        self.status.pack(pady=(6, 0))

        self.outputs_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=10),
            text_color=("gray35", "gray65"), justify="center",
        )
        self.outputs_label.pack(pady=(2, 0))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(pady=(12, 6), padx=24, fill="x")
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        self.open_btn = ctk.CTkButton(
            actions, text="Open folder",
            fg_color="transparent", border_width=1, corner_radius=10,
            state="disabled", command=self.open_output,
        )
        self.open_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.open_gif_btn = ctk.CTkButton(
            actions, text="Open GIF",
            fg_color="transparent", border_width=1, corner_radius=10,
            state="disabled", command=self.open_gif,
        )
        self.open_gif_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.share_btn = ctk.CTkButton(
            self, text="Send to phone (QR)",
            fg_color="transparent",
            border_width=1,
            corner_radius=10,
            state="disabled",
            command=self.open_share_window,
        )
        self.share_btn.pack(pady=(0, 20), padx=24, fill="x")

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
        self.open_gif_btn.configure(state="disabled")
        self.share_btn.configure(state="disabled")
        self.outputs_label.configure(text="")
        self.status.configure(text="Starting…")
        self.progress.start()
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
        self.progress.stop()
        self.progress.set(0)
        self.status.configure(text="Done.")
        self.outputs_label.configure(text=f"Saved: {self.last_outputs.name}")
        self.make_btn.configure(state="normal", text="Make GIF")
        self.open_btn.configure(state="normal")
        self.open_gif_btn.configure(state="normal")
        self.share_btn.configure(state="normal")

    def _on_failure(self, msg: str) -> None:
        self.progress.stop()
        self.progress.set(0)
        self.status.configure(text="Failed.")
        self.make_btn.configure(state="normal", text="Make GIF")
        messagebox.showerror("Failed", msg)

    def open_output(self) -> None:
        folder = self.last_outputs.parent if self.last_outputs else output_dir()
        try:
            os.startfile(folder)
        except AttributeError:
            subprocess.Popen(["xdg-open", str(folder)])

    def open_gif(self) -> None:
        if not self.last_outputs or not self.last_outputs.exists():
            messagebox.showerror("No GIF", "Make a GIF first.")
            return
        try:
            os.startfile(str(self.last_outputs))
        except AttributeError:
            subprocess.Popen(["xdg-open", str(self.last_outputs)])

    def open_share_window(self) -> None:
        if not self.last_outputs or not self.last_outputs.exists():
            messagebox.showerror("No GIF", "Make a GIF first.")
            return
        try:
            session = serve_file(self.last_outputs)
        except OSError as e:
            messagebox.showerror("Network error", f"Could not start local server:\n{e}")
            return
        ShareWindow(self, session)


class ShareWindow(ctk.CTkToplevel):
    def __init__(self, master: ctk.CTk, session: ShareSession) -> None:
        super().__init__(master)
        self.title("Send to phone")
        self.geometry("420x600")
        self.resizable(False, False)
        self.session = session
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        ctk.CTkLabel(
            self, text="Scan with your phone",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(20, 4))

        ctk.CTkLabel(
            self,
            text="Phone must be on the same Wi-Fi.\nWindows may ask to allow the firewall — click Allow.",
            font=ctk.CTkFont(size=11),
            text_color=("gray35", "gray65"),
            justify="center",
        ).pack(pady=(0, 12))

        qr_img = qrcode.make(session.url)
        pil_img = qr_img.get_image() if hasattr(qr_img, "get_image") else qr_img
        pil_img = pil_img.convert("RGB").resize((320, 320), Image.NEAREST)
        self._qr_photo = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(320, 320))

        ctk.CTkLabel(self, image=self._qr_photo, text="").pack(pady=(0, 12))

        url_box = ctk.CTkTextbox(self, height=44, width=360, font=ctk.CTkFont(size=11))
        url_box.insert("1.0", session.url)
        url_box.configure(state="disabled")
        url_box.pack(pady=(0, 12), padx=20)

        ctk.CTkButton(
            self, text="Stop sharing",
            corner_radius=10,
            command=self._on_close,
        ).pack(pady=(0, 16), padx=20, fill="x")

    def _on_close(self) -> None:
        try:
            self.session.stop()
        finally:
            self.destroy()


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
