# UTM Audio Splitter

🎵 **Extract audio from video, split audio by duration or file size** — all offline, no upload required.

Choose your tool:

- **🖥️ Desktop App** (Windows / macOS / Linux) — drag-and-drop GUI with real-time progress
- **📜 CLI Scripts** — light-weight shell scripts for quick splitting

---

## 🖥️ Desktop GUI App (Cross-Platform)

A modern desktop application with drag-and-drop support, real-time progress bars, and three processing modes.

### Features

| Feature | Description |
|---------|-------------|
| **Drag & Drop** | Drop audio/video files directly onto the app |
| **Video → Audio** | Extract audio from `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm` |
| **Split by Duration** | Cut audio into equal-length segments (e.g. 5 min each) |
| **Split by Size** | Split audio to stay under a file size limit (e.g. 25 MB for OpenAI Whisper) |
| **Format Selection** | Output as MP3, WAV, or M4A |
| **Progress Tracking** | Real-time progress bar and detailed log |
| **Cross-Platform** | Runs on Windows, macOS, and Linux |

### Quick Start (Desktop App)

```bash
# 1. Install Python 3.10+ and ffmpeg
# 2. Install the app
pip install -r requirements.txt

# 3. Launch
python app.py
```

> **Tip:** Use `build.py` to package a standalone executable with PyInstaller:
> ```bash
> python build.py
> ```
> The bundled `.exe` / `.app` / binary lands in `dist/` — no Python required to run it.

### Screenshot

```
┌─────────────────────────────────────────────┐
│  🎵 UTM Audio Splitter                      │
│  Extract, split, and convert audio offline   │
├─────────────────────────────────────────────┤
│ 📁 Input Files                              │
│ ┌─────────────────────────────────────┐ 📁  │
│ │ Drag & drop files here             │    │
│ └─────────────────────────────────────┘    │
│ 3 file(s): .mp3, .mp4, .wav  [Clear]     │
├─────────────────────────────────────────────┤
│ Processing Mode                             │
│ ○ 🎧 Extract Audio                         │
│ ○ ⏱ Split by Duration                     │
│ ● 📦 Split by Size     Max: [ 25 ] MB    │
├─────────────────────────────────────────────┤
│ Output Directory: /Users/me/Desktop/Output  │
├─────────────────────────────────────────────┤
│ [▶ Start Processing]  [✕ Cancel]           │
│ ████████████████░░░░░░ 75%                 │
├─────────────────────────────────────────────┤
│ Output Log                                  │
│ $ ffmpeg -i lecture.mp4 -vn ...            │
│ ✓ Audio extracted.                          │
│ → Bitrate: 128000 bps → segment ~300s      │
└─────────────────────────────────────────────┘
```

### Supported Input Formats

**Audio:** `.mp3`, `.m4a`, `.aac`, `.wav`, `.flac`, `.ogg`
**Video:** `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`

---

## 📜 CLI Scripts (Light-weight)

For users who prefer the terminal or need a zero-dependency splitter.

| Platform | Script | How to Run |
|----------|--------|------------|
| Windows | [`audio-splitter-windows.bat`](audio-splitter-windows.bat) | Double-click |
| macOS | [`audio-splitter-macos.command`](audio-splitter-macos.command) | `chmod +x && ./` |
| Linux | [`audio-splitter-linux.sh`](audio-splitter-linux.sh) | `chmod +x && ./` |

Each script:
1. Auto-installs `ffmpeg` if missing
2. Scans the current folder for supported files **larger than 100 MB**
3. Splits each into **~50 MB** parts
4. For `.mp4` files, extracts audio → splits to MP3

---

## Requirements

- **ffmpeg** / **ffprobe** — the GUI app warns if missing; CLI scripts attempt auto-installation
- **Python 3.10+** (only for the GUI app)
- **customtkinter** (auto-installed via `pip install -r requirements.txt`)

## Output

Parts are named `{original}_part_001.{ext}`, `{original}_part_002.{ext}`, etc. and placed in your chosen output directory.

Existing split parts are overwritten on re-run.

## Version

**2026.07.29**

## License

MIT — do what you want with it.
