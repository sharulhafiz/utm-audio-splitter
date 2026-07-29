# UTM Audio Splitter

Offline scripts that split large audio/video files into smaller parts using `ffmpeg` — no upload required.

## Supported Formats

| Format | Extension | Behaviour |
|--------|-----------|-----------|
| MP3 | `.mp3` | Split into ~50MB parts (copy, no re-encode) |
| M4A | `.m4a` | Split into ~50MB parts (copy, no re-encode) |
| AAC | `.aac` | Split into ~50MB parts (copy, no re-encode) |
| WAV | `.wav` | Split into ~50MB parts (copy, no re-encode) |
| FLAC | `.flac` | Split into ~50MB parts (copy, no re-encode) |
| OGG | `.ogg` | Split into ~50MB parts (copy, no re-encode) |
| MP4 | `.mp4` | Audio extracted → split into ~50MB **MP3** parts (re-encode) |

## Requirements

- **ffmpeg** and **ffprobe** (each script attempts auto-installation if missing)
- Files **larger than 100MB** — smaller files are skipped

## Usage

### Windows

1. Download [`audio-splitter-windows.bat`](audio-splitter-windows.bat)
2. Place it in the folder with your audio/video files
3. Double-click `audio-splitter-windows.bat`
4. Allow the Windows SmartScreen prompt if it appears
5. Let the script run — split parts appear in the same folder

### macOS

1. Download [`audio-splitter-macos.command`](audio-splitter-macos.command)
2. Open Terminal and navigate to your files folder:
   ```bash
   cd /path/to/your/files
   ```
3. Make the script executable and run it:
   ```bash
   chmod +x /path/to/audio-splitter-macos.command
   ./audio-splitter-macos.command
   ```
4. Allow the Gatekeeper prompt if it appears (Right-click → Open if blocked)
5. The script auto-installs `ffmpeg` via Homebrew if missing

### Linux

1. Download [`audio-splitter-linux.sh`](audio-splitter-linux.sh)
2. Open a terminal and navigate to your files folder:
   ```bash
   cd /path/to/your/files
   ```
3. Make the script executable and run it:
   ```bash
   chmod +x /path/to/audio-splitter-linux.sh
   ./audio-splitter-linux.sh
   ```
4. The script auto-installs `ffmpeg` via your package manager if missing
   (supports `apt`, `dnf`, `yum`, `pacman`, `zypper`, `apk`)

## How It Works

1. **Checks for ffmpeg** — installs it automatically if not found
2. **Scans the current folder** — finds supported files larger than 100MB
3. **Splits each file** — into approximately 50MB parts using ffmpeg
4. **Outputs parts** — named as `{original}_part_001.{ext}`, `{original}_part_002.{ext}`, etc.
5. **Overwrites existing parts** — if you re-run, previous split parts are replaced

For MP4 files, the script extracts the audio track and splits it into MP3 parts (192kbps).

## Output

Parts are placed in the **same folder** as the source files:

```
your-song.mp3                    ← original (300MB)
your-song_part_001.mp3           ← ~50MB
your-song_part_002.mp3           ← ~50MB
your-song_part_003.mp3           ← ~50MB
...
```

## Version

**2026.03.04**

## License

MIT — do what you want with it.
