# UTM Audio Splitter

🎵 **Extract audio from video, split by duration or file size** — all offline, no upload required.

Choose your weapon:

- **🖥️ Desktop App** — drag-and-drop GUI (Windows / macOS / Linux) — **download & run, no setup needed**
- **📜 CLI Scripts** — light-weight shell scripts for quick terminal splitting

---

## 🖥️ Desktop App (Electron)

A cross-platform desktop application with zero dependencies. Download, install, run.

### Download

| Platform | Format | How to Run |
|----------|--------|------------|
| Windows | `.exe` (portable) | Double-click `UTM Audio Splitter.exe` |
| macOS | `.dmg` | Open DMG, drag to Applications, launch |
| Linux | `.AppImage` | `chmod +x && ./UTM\ Audio\ Splitter-*.AppImage` |

> **Build from source** if no prebuilt release is available (see [Building](#building) below).

### Features

| Feature | |
|---------|--|
| **Drag & Drop** | Drop files onto the app or click Browse |
| **Video → Audio** | Extract audio from `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm` |
| **Split by Duration** | Cut audio into equal time segments (configurable seconds) |
| **Split by File Size** | Auto-calculates segment time from bitrate to stay under a size limit |
| **Format Selection** | Output as MP3, WAV, or M4A |
| **Progress Bar** | Real-time progress tracking per file |
| **Output Log** | Full ffmpeg command log for transparency |
| **Cancel** | Stop mid-operation |
| **No Dependencies** | Everything bundled — not even Python or Node needed |

### Screenshot

```
┌─────────────────────────────────────────────────────┐
│  🎵 UTM Audio Splitter                              │
│  Extract, split, and convert audio — no upload      │
├─────────────────────────────────────────────────────┤
│  📁 Input Files                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  📁 Drag & drop audio/video files here       │    │
│  │              or                              │    │
│  │        [ Browse Files ]                      │    │
│  └─────────────────────────────────────────────┘    │
│  lecture.mp4  song.mp3  podcast.wav                │
│  3 file(s): .mp4, .mp3, .wav                       │
├─────────────────────────────────────────────────────┤
│  Processing Mode                                    │
│  (●) 🎧 Extract Audio                              │
│  ( ) ⏱ Split by Duration                          │
│  ( ) 📦 Split by Size                             │
│                                                     │
│  Output format: [MP3 (.mp3) ▼]                     │
├─────────────────────────────────────────────────────┤
│  📂 Output Directory                                │
│  /Users/me/Desktop/SplitAudio    [ Browse ]        │
├─────────────────────────────────────────────────────┤
│  [▶ Start Processing]  [✕ Cancel]                  │
│  ████████████████████░░░░░░░░  75%                 │
├─────────────────────────────────────────────────────┤
│  Output Log                                         │
│  ▶ Processing started...                            │
│  ffmpeg -i lecture.mp4 -vn -acodec ...             │
│  ✓ Audio extracted.                                 │
└─────────────────────────────────────────────────────┘
```

---

## 📜 CLI Scripts (Light-weight)

For headless servers or users who prefer the terminal.

| Platform | Script | How to Run |
|----------|--------|------------|
| Windows | [`audio-splitter-windows.bat`](audio-splitter-windows.bat) | Double-click |
| macOS | [`audio-splitter-macos.command`](audio-splitter-macos.command) | `chmod +x && ./` |
| Linux | [`audio-splitter-linux.sh`](audio-splitter-linux.sh) | `chmod +x && ./` |

Each script auto-installs `ffmpeg` if missing, then splits files >100MB into ~50MB parts.

---

## Building from Source

If you want to build the desktop app yourself (e.g. to customize or for a release):

```bash
# Prerequisites: Node.js 18+
git clone https://github.com/sharulhafiz/utm-audio-splitter.git
cd utm-audio-splitter

# Install dependencies
npm install

# Run in development mode
npm start

# Build portable binaries
npm run build:win      # Windows portable .exe
npm run build:mac      # macOS .dmg
npm run build:linux    # Linux .AppImage
npm run build:all      # All platforms
```

Output lands in `dist/`.

## Requirements

- **Desktop App**: None — everything is bundled (Electron runtime + ffmpeg binaries)
- **CLI Scripts**: `ffmpeg` / `ffprobe` must be installed (scripts attempt auto-installation)

## Output

Parts are named `{original}_part_001.{ext}`, `{original}_part_002.{ext}`, etc. in your chosen output directory.

Existing split parts are overwritten on re-run.

## Version

**2026.07.29**

## License

MIT — do what you want with it.
