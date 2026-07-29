#!/usr/bin/env python3
"""
UTM Audio Splitter — Cross-Platform Desktop GUI

Extract audio from video, split audio by duration or file size,
all via a clean drag-and-drop interface powered by ffmpeg.

Supports: Windows, macOS, Linux
"""

from __future__ import annotations

import math
import os
import re
import subprocess
import sys
import threading
import time
import json
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────
APP_NAME = "UTM Audio Splitter"
APP_VERSION = "2026.07.29"

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}
ALL_INPUT_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

SUPPORTED_OUTPUT_FORMATS = {
    "MP3 (.mp3)": "mp3",
    "WAV (.wav)": "wav",
    "M4A (.m4a)": "m4a",
}

FFMPEG_BITRATE_MAP = {
    "mp3": "libmp3lame",
    "wav": "pcm_s16le",
    "m4a": "aac",
}

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("green")


# ──────────────────────────────────────────────
# FFmpeg detection
# ──────────────────────────────────────────────
def _ffmpeg_path() -> str:
    """Return path to ffmpeg binary, or raise FileNotFoundError."""
    for cmd in ("ffmpeg", "ffmpeg.exe"):
        for path in os.environ["PATH"].split(os.pathsep):
            full = os.path.join(path.strip('"'), cmd)
            if os.path.isfile(full) and os.access(full, os.X_OK):
                return full
    raise FileNotFoundError(
        "ffmpeg not found. Install ffmpeg and ensure it is on your PATH."
    )


def _ffprobe_path() -> str:
    """Return path to ffprobe binary, or raise FileNotFoundError."""
    for cmd in ("ffprobe", "ffprobe.exe"):
        for path in os.environ["PATH"].split(os.pathsep):
            full = os.path.join(path.strip('"'), cmd)
            if os.path.isfile(full) and os.access(full, os.X_OK):
                return full
    raise FileNotFoundError(
        "ffprobe not found. Install ffmpeg and ensure it is on your PATH."
    )


# ──────────────────────────────────────────────
# FFprobe helpers
# ──────────────────────────────────────────────
def _get_bitrate_bps(file_path: str) -> int:
    """Detect audio stream bitrate (fallback to format bitrate, then 128k)."""
    try:
        cmd = [
            _ffprobe_path(),
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=bit_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        br = res.stdout.strip()
        if br.isdigit() and int(br) > 0:
            return int(br)

        cmd[3:5] = ["-show_entries", "format=bit_rate"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        br = res.stdout.strip()
        if br.isdigit() and int(br) > 0:
            return int(br)
    except Exception:
        pass
    return 128_000


def _get_duration_seconds(file_path: str) -> float:
    """Get media duration in seconds via ffprobe."""
    cmd = [
        _ffprobe_path(),
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    val = res.stdout.strip()
    try:
        dur = float(val)
        return dur if dur > 0 else 0.0
    except ValueError:
        return 0.0


# ──────────────────────────────────────────────
# Data model for a processing job
# ──────────────────────────────────────────────
@dataclass
class JobConfig:
    input_paths: list[str] = field(default_factory=list)
    output_dir: str = ""
    mode: str = "extract"  # extract | split_duration | split_size
    target_format: str = "mp3"  # for extract mode
    segment_seconds: int = 300  # for split_duration mode (default 5 min)
    max_size_mb: int = 25  # for split_size mode (default 25 MB)
    extract_only: bool = False  # extract audio without splitting


# ──────────────────────────────────────────────
# Background processor (runs ffmpeg in a thread)
# ──────────────────────────────────────────────
class AudioProcessor:
    """Process files in a background thread, emitting progress callbacks."""

    def __init__(
        self,
        config: JobConfig,
        progress_callback: callable,
        log_callback: callable,
        done_callback: callable,
    ):
        self.config = config
        self.on_progress = progress_callback
        self.on_log = log_callback
        self.on_done = done_callback
        self._cancel = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def cancel(self):
        self._cancel.set()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        self._cancel.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            self._process_all()
        except Exception as exc:
            self.on_done(False, str(exc))
        else:
            self.on_done(True, "All files processed successfully.")

    def _process_all(self):
        cfg = self.config
        total = len(cfg.input_paths)
        for idx, file_path in enumerate(cfg.input_paths):
            if self._cancel.is_set():
                self.on_done(False, "Cancelled by user.")
                return

            base_name = Path(file_path).stem
            ext = Path(file_path).suffix.lower()
            self.on_log(f"\n[{idx + 1}/{total}] Processing: {Path(file_path).name}")

            # Step 1: If video, extract audio first
            audio_source = file_path
            temp_wav: Optional[str] = None

            if ext in VIDEO_EXTENSIONS:
                temp_wav = os.path.join(
                    cfg.output_dir, f"__temp_{base_name}_{int(time.time())}.wav"
                )
                self.on_log("→ Extracting audio from video...")
                self._run_ffmpeg(
                    [
                        _ffmpeg_path(),
                        "-hide_banner", "-loglevel", "error",
                        "-i", file_path,
                        "-vn",
                        "-map", "0:a:0",
                        "-acodec", "pcm_s16le",
                        "-y", temp_wav,
                    ],
                    desc=f"Extracting audio: {Path(file_path).name}",
                )
                audio_source = temp_wav
                ext = ".wav"
                self.on_log("✓ Audio extracted.")

            if self._cancel.is_set():
                self._cleanup_temp(temp_wav)
                return

            # Step 2: Process according to mode
            if cfg.mode == "extract":
                self._extract_audio(audio_source, cfg, base_name, idx, total)
            elif cfg.mode == "split_duration":
                self._split_duration(audio_source, cfg, base_name, ext, idx, total)
            elif cfg.mode == "split_size":
                self._split_size(audio_source, cfg, base_name, ext, idx, total)

            self._cleanup_temp(temp_wav)

    def _extract_audio(
        self, source: str, cfg: JobConfig, base_name: str, idx: int, total: int
    ):
        out_name = f"{base_name}.{cfg.target_format}"
        out_path = os.path.join(cfg.output_dir, out_name)

        if self._cancel.is_set():
            return

        codec = FFMPEG_BITRATE_MAP.get(cfg.target_format, "libmp3lame")
        cmd = [
            _ffmpeg_path(),
            "-hide_banner", "-loglevel", "error",
            "-i", source,
            "-vn",
            "-map", "0:a:0",
            "-acodec", codec,
            "-y", out_path,
        ]
        self._run_ffmpeg(cmd, desc=f"Converting: {Path(source).name} → {out_name}")

    def _split_duration(
        self, source: str, cfg: JobConfig, base_name: str, ext: str, idx: int, total: int
    ):
        seg = max(1, cfg.segment_seconds)
        out_pattern = os.path.join(cfg.output_dir, f"{base_name}_part_%03d{ext}")

        self._cleanup_existing_parts(cfg.output_dir, base_name, ext)

        cmd = [
            _ffmpeg_path(),
            "-hide_banner", "-loglevel", "error",
            "-i", source,
            "-f", "segment",
            "-segment_time", str(seg),
            "-reset_timestamps", "1",
            "-c", "copy",
            "-y", out_pattern,
        ]
        self._run_ffmpeg(cmd, desc=f"Splitting by {seg}s: {Path(source).name}")

    def _split_size(
        self, source: str, cfg: JobConfig, base_name: str, ext: str, idx: int, total: int
    ):
        max_bytes = cfg.max_size_mb * 1024 * 1024
        bitrate = _get_bitrate_bps(source)
        seg = max(1, (max_bytes * 8) // bitrate) if bitrate > 0 else 300
        out_pattern = os.path.join(cfg.output_dir, f"{base_name}_part_%03d{ext}")

        self._cleanup_existing_parts(cfg.output_dir, base_name, ext)

        self.on_log(f"→ Bitrate: {bitrate} bps → segment ~{seg}s (max {cfg.max_size_mb}MB)")

        cmd = [
            _ffmpeg_path(),
            "-hide_banner", "-loglevel", "error",
            "-i", source,
            "-f", "segment",
            "-segment_time", str(seg),
            "-reset_timestamps", "1",
            "-c", "copy",
            "-y", out_pattern,
        ]
        self._run_ffmpeg(cmd, desc=f"Splitting ≤{cfg.max_size_mb}MB: {Path(source).name}")

    def _run_ffmpeg(self, cmd: list[str], desc: str = ""):
        """Run an ffmpeg command, parsing progress for the callback."""
        if self._cancel.is_set():
            return

        self.on_log(f"$ {' '.join(cmd)}")
        self.on_progress(0, desc or "Processing...")

        duration = 0.0
        # Try to detect duration for progress reporting
        try:
            idx = cmd.index("-i") + 1
            src = cmd[idx]
            duration = _get_duration_seconds(src)
        except (ValueError, IndexError):
            pass

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # ffmpeg outputs progress on stderr
        time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
        last_report = 0.0

        assert process.stderr is not None
        for line in iter(process.stderr.readline, ""):
            if self._cancel.is_set():
                process.terminate()
                return

            m = time_pattern.search(line)
            if m:
                h, mnt, s = m.groups()
                elapsed = int(h) * 3600 + int(mnt) * 60 + float(s)
                if duration > 0 and elapsed - last_report >= 1.0:
                    pct = min(99, int((elapsed / duration) * 100))
                    self.on_progress(pct, desc or "Processing...")
                    last_report = elapsed

        process.wait()

        if process.returncode != 0 and not self._cancel.is_set():
            stderr_out = process.stderr.read() if process.stderr else ""
            raise RuntimeError(
                f"ffmpeg failed (code {process.returncode}):\n{stderr_out[:500]}"
            )

        self.on_progress(100, desc or "Done.")

    @staticmethod
    def _cleanup_existing_parts(out_dir: str, base: str, ext: str):
        pattern = os.path.join(out_dir, f"{base}_part_*{ext}")
        for f in Path(out_dir).glob(f"{base}_part_*{ext}"):
            try:
                f.unlink()
            except OSError:
                pass

    @staticmethod
    def _cleanup_temp(path: Optional[str]):
        if path and os.path.isfile(path):
            try:
                os.unlink(path)
            except OSError:
                pass


# ──────────────────────────────────────────────
# GUI Application
# ──────────────────────────────────────────────
class App(ctk.CTk):
    TITLE = f"{APP_NAME} v{APP_VERSION}"

    def __init__(self):
        super().__init__()
        self.title(self.TITLE)
        self.minsize(720, 600)
        self.geometry("800x700")

        # State
        self.selected_files: list[str] = []
        self.processor: Optional[AudioProcessor] = None
        self._job_active = False

        # ── Layout ────────────────────────────
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_input_section()
        self._build_mode_section()
        self._build_output_section()
        self._build_action_section()
        self._build_log_section()

        # Final checks
        self._update_ui_state()

    # ── Header ────────────────────────────────
    def _build_header(self):
        frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 4))
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text="🎵 UTM Audio Splitter",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            frame,
            text="Extract, split, and convert audio — no upload required",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, sticky="w")

    # ── Input / File selection ────────────────
    def _build_input_section(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(8, 4))
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Input Files", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(4, 6)
        )

        self.drop_zone = ctk.CTkTextbox(
            frame,
            height=70,
            corner_radius=8,
            border_width=2,
            border_color="#888",
            fg_color=("gray95", "gray20"),
        )
        self.drop_zone.grid(row=1, column=0, columnspan=3, sticky="ew", padx=(0, 8))
        self.drop_zone.insert("0.0", "Drag & drop audio/video files here, or click Browse")
        self.drop_zone.configure(state="disabled")

        self.btn_browse = ctk.CTkButton(frame, text="📁 Browse", width=100, command=self._browse_files)
        self.btn_browse.grid(row=1, column=3, padx=(0, 0))

        self.file_label = ctk.CTkLabel(frame, text="No files selected", anchor="w")
        self.file_label.grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 4))

        self.btn_clear = ctk.CTkButton(frame, text="Clear", width=70, fg_color="gray40",
                                       command=self._clear_files)
        self.btn_clear.grid(row=2, column=3, sticky="e")

        # Enable drag-and-drop via <Drop> event binding
        self.drop_zone.bind("<Button-1>", lambda e: self._browse_files())
        # CustomTkinter doesn't have native DnD; we bind a virtual event
        self.bind_all("<<FileDrop>>", self._on_filedrop)

    def _browse_files(self):
        files = filedialog.askopenfilenames(
            title="Select audio/video files",
            filetypes=[
                ("Media files", " *.mp3 *.m4a *.aac *.wav *.flac *.ogg *.mp4 *.mkv *.mov *.avi *.webm"),
                ("Audio files", " *.mp3 *.m4a *.aac *.wav *.flac *.ogg"),
                ("Video files", " *.mp4 *.mkv *.mov *.avi *.webm"),
                ("All files", " *.*"),
            ],
        )
        if files:
            self._set_files(list(files))

    def _on_filedrop(self, event):
        # Expects event.data to be a newline-separated list of file paths
        raw = getattr(event, "data", "")
        paths = [p.strip() for p in raw.split("\n") if p.strip()]
        valid = [p for p in paths if Path(p).suffix.lower() in ALL_INPUT_EXTENSIONS]
        if valid:
            self._set_files(valid)

    def _set_files(self, files: list[str]):
        self.selected_files = files
        count = len(files)
        exts = set(Path(f).suffix.lower() for f in files)
        info = f"{count} file(s): {', '.join(sorted(exts))}"
        self.file_label.configure(text=info)
        self._update_ui_state()

    def _clear_files(self):
        self.selected_files = []
        self.file_label.configure(text="No files selected")
        self._update_ui_state()

    # ── Mode selection ────────────────────────
    def _build_mode_section(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 4))
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Processing Mode", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(4, 6)
        )

        self.mode_var = ctk.StringVar(value="extract")

        modes = [
            ("🎧 Extract Audio", "extract", "Extract audio track from video files"),
            ("⏱ Split by Duration", "split_duration", "Split audio into equal time segments"),
            ("📦 Split by Size", "split_size", "Split audio to fit a max file size (e.g. 25MB for Whisper)"),
        ]

        for i, (label, value, hint) in enumerate(modes):
            rb = ctk.CTkRadioButton(
                frame, text=label, value=value, variable=self.mode_var,
                command=self._on_mode_change,
            )
            rb.grid(row=i + 1, column=0, sticky="w", padx=(0, 12), pady=2)
            ctk.CTkLabel(frame, text=hint, font=ctk.CTkFont(size=11), text_color="gray").grid(
                row=i + 1, column=1, sticky="w"
            )

        # ── Config fields ──
        self.config_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.config_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        self.config_frame.grid_columnconfigure(1, weight=1)

        # Target format (for extract mode)
        ctk.CTkLabel(self.config_frame, text="Output format:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.format_var = ctk.StringVar(value="MP3 (.mp3)")
        self.format_menu = ctk.CTkOptionMenu(
            self.config_frame, values=list(SUPPORTED_OUTPUT_FORMATS.keys()),
            variable=self.format_var, width=120,
        )
        self.format_menu.grid(row=0, column=1, sticky="w")

        # Duration input (for split_duration mode)
        ctk.CTkLabel(self.config_frame, text="Segment duration (seconds):").grid(
            row=1, column=0, sticky="w", padx=(0, 8)
        )
        self.duration_var = ctk.StringVar(value="300")
        self.duration_entry = ctk.CTkEntry(self.config_frame, textvariable=self.duration_var, width=100)
        self.duration_entry.grid(row=1, column=1, sticky="w")

        # Size input (for split_size mode)
        ctk.CTkLabel(self.config_frame, text="Max file size (MB):").grid(
            row=2, column=0, sticky="w", padx=(0, 8)
        )
        self.size_var = ctk.StringVar(value="25")
        self.size_entry = ctk.CTkEntry(self.config_frame, textvariable=self.size_var, width=100)
        self.size_entry.grid(row=2, column=1, sticky="w")

        self._on_mode_change()

    def _on_mode_change(self):
        mode = self.mode_var.get()
        self.format_menu.grid_remove()
        self.duration_entry.grid_remove()
        self.size_entry.grid_remove()
        for i in range(3):
            self.config_frame.grid_slaves(row=i, column=0)[0].grid_remove()
            self.config_frame.grid_slaves(row=i, column=1)[0].grid_remove()

        # Show relevant controls
        ctk.CTkLabel(self.config_frame, text="Output format:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.format_menu.grid(row=0, column=1, sticky="w")

        if mode == "split_duration":
            ctk.CTkLabel(self.config_frame, text="Segment duration (seconds):").grid(
                row=1, column=0, sticky="w", padx=(0, 8)
            )
            self.duration_entry.grid(row=1, column=1, sticky="w")

        elif mode == "split_size":
            ctk.CTkLabel(self.config_frame, text="Max file size (MB):").grid(
                row=1, column=0, sticky="w", padx=(0, 8)
            )
            self.size_entry.grid(row=1, column=1, sticky="w")

    # ── Output directory ──────────────────────
    def _build_output_section(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 4))
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Output Directory", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(4, 6)
        )

        self.output_dir_var = ctk.StringVar(value=str(Path.home() / "Desktop" / "SplitAudio"))
        self.output_entry = ctk.CTkEntry(frame, textvariable=self.output_dir_var)
        self.output_entry.grid(row=1, column=1, sticky="ew", padx=(0, 8))

        self.btn_output = ctk.CTkButton(frame, text="📂 Browse", width=100, command=self._browse_output)
        self.btn_output.grid(row=1, column=2)

    def _browse_output(self):
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self.output_dir_var.set(d)

    # ── Action bar ────────────────────────────
    def _build_action_section(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=4, column=0, sticky="ew", padx=20, pady=(8, 4))
        frame.grid_columnconfigure(0, weight=1)

        self.btn_start = ctk.CTkButton(
            frame, text="▶ Start Processing", height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._start_processing,
        )
        self.btn_start.grid(row=0, column=0, sticky="w")

        self.btn_cancel = ctk.CTkButton(
            frame, text="✕ Cancel", height=40, fg_color="gray40",
            state="disabled", command=self._cancel_processing,
        )
        self.btn_cancel.grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.progress_bar = ctk.CTkProgressBar(frame, width=300)
        self.progress_bar.grid(row=0, column=2, sticky="ew", padx=(16, 8))
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(frame, text="Ready", anchor="w", width=180)
        self.progress_label.grid(row=0, column=3, sticky="w")

    # ── Log ───────────────────────────────────
    def _build_log_section(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=5, column=0, sticky="nsew", padx=20, pady=(4, 16))
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Output Log", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(4, 4)
        )

        self.log_box = ctk.CTkTextbox(frame, state="disabled", wrap="word")
        self.log_box.grid(row=1, column=0, sticky="nsew")

    # ── UI state management ───────────────────
    def _update_ui_state(self):
        has_files = len(self.selected_files) > 0
        self.btn_start.configure(state="normal" if has_files and not self._job_active else "disabled")
        self.btn_cancel.configure(state="normal" if self._job_active else "disabled")
        self.btn_browse.configure(state="normal" if not self._job_active else "disabled")
        self.btn_clear.configure(state="normal" if has_files and not self._job_active else "disabled")
        self.btn_output.configure(state="normal" if not self._job_active else "disabled")

    # ── Processing ────────────────────────────
    def _log(self, msg: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self.update_idletasks()

    def _start_processing(self):
        if not self.selected_files:
            return

        try:
            _ffmpeg_path()
            _ffprobe_path()
        except FileNotFoundError as e:
            messagebox.showerror("FFmpeg Not Found",
                                 f"{e}\n\nPlease install ffmpeg and make sure it's available in your PATH.")
            return

        mode = self.mode_var.get()
        out_dir = self.output_dir_var.get().strip()
        if not out_dir:
            out_dir = str(Path.home() / "Desktop" / "SplitAudio")
            self.output_dir_var.set(out_dir)

        os.makedirs(out_dir, exist_ok=True)

        cfg = JobConfig(
            input_paths=self.selected_files.copy(),
            output_dir=out_dir,
            mode=mode,
            target_format=SUPPORTED_OUTPUT_FORMATS[self.format_var.get()],
        )

        if mode == "split_duration":
            try:
                cfg.segment_seconds = int(self.duration_var.get())
                if cfg.segment_seconds < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid Input", "Segment duration must be a positive integer (seconds).")
                return

        if mode == "split_size":
            try:
                cfg.max_size_mb = int(self.size_var.get())
                if cfg.max_size_mb < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid Input", "Max file size must be a positive integer (MB).")
                return

        self._job_active = True
        self._update_ui_state()
        self.progress_bar.set(0)
        self.progress_label.configure(text="Starting...")
        self.log_box.configure(state="normal")
        self.log_box.delete("0.0", "end")
        self.log_box.configure(state="disabled")

        self.processor = AudioProcessor(
            config=cfg,
            progress_callback=self._on_progress,
            log_callback=self._log,
            done_callback=self._on_done,
        )
        self.processor.start()

    def _cancel_processing(self):
        if self.processor:
            self._log("\n✕ Cancelling...")
            self.processor.cancel()

    def _on_progress(self, pct: int, desc: str):
        self.progress_bar.set(pct / 100)
        self.progress_label.configure(text=f"{desc} ({pct}%)")
        self.update_idletasks()

    def _on_done(self, success: bool, message: str):
        self._job_active = False
        self._update_ui_state()

        if success:
            self.progress_bar.set(1)
            self.progress_label.configure(text="✅ Complete!")
            self._log(f"\n✅ {message}")
        else:
            self.progress_bar.set(0)
            self.progress_label.configure(text="❌ Failed")
            self._log(f"\n❌ {message}")
            messagebox.showerror("Processing Error", message)

        self.processor = None
        self._update_ui_state()


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
def main():
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("green")
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
