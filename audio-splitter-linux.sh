#!/bin/bash
set -euo pipefail

SCRIPT_VERSION="2026.09.18"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo " Audio Splitter - Linux"
echo " Version: ${SCRIPT_VERSION}"
echo " Folder: $(pwd)"
echo "============================================"
echo ""

SOURCE_MIN_BYTES=$((100 * 1024 * 1024))
TARGET_CHUNK_BYTES=$((50 * 1024 * 1024))
MP4_OUTPUT_BITRATE_BPS=192000
AUDIO_REGEX='\.(mp3|m4a|aac|wav|flac|ogg)$'
VIDEO_REGEX='\.(mp4)$'

ensure_ffmpeg() {
    if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
        return
    fi

    echo "ffmpeg/ffprobe not found. Attempting installation..."
    echo ""

    # Prefer sudo if available, fallback to su -c
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        SUDO="su -c"
    fi

    # Detect package manager
    if command -v apt-get >/dev/null 2>&1; then
        echo "Detected Debian/Ubuntu (apt). Installing ffmpeg..."
        $SUDO apt-get update -qq
        $SUDO apt-get install -y -qq ffmpeg
    elif command -v dnf >/dev/null 2>&1; then
        echo "Detected Fedora/RHEL (dnf). Installing ffmpeg..."
        $SUDO dnf install -y ffmpeg
    elif command -v yum >/dev/null 2>&1; then
        echo "Detected RHEL/CentOS (yum). Installing ffmpeg..."
        $SUDO yum install -y ffmpeg
    elif command -v pacman >/dev/null 2>&1; then
        echo "Detected Arch Linux (pacman). Installing ffmpeg..."
        $SUDO pacman -S --noconfirm ffmpeg
    elif command -v zypper >/dev/null 2>&1; then
        echo "Detected openSUSE (zypper). Installing ffmpeg..."
        $SUDO zypper --non-interactive install ffmpeg
    elif command -v apk >/dev/null 2>&1; then
        echo "Detected Alpine Linux (apk). Installing ffmpeg..."
        $SUDO apk add --no-cache ffmpeg
    else
        echo "Could not detect package manager."
        echo "Please install ffmpeg manually, then run this script again."
        echo ""
        echo "  Debian/Ubuntu: sudo apt-get install ffmpeg"
        echo "  Fedora:        sudo dnf install ffmpeg"
        echo "  Arch Linux:    sudo pacman -S ffmpeg"
        echo "  openSUSE:      sudo zypper install ffmpeg"
        read -r -p "Press Enter to close..."
        exit 1
    fi

    echo ""

    if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
        echo "ffmpeg/ffprobe still unavailable after installation."
        echo "Please install it manually, then open this script again."
        read -r -p "Press Enter to close..."
        exit 1
    fi

    echo "ffmpeg installed successfully."
}

get_bitrate_bps() {
    local file="$1"
    local stream_bitrate
    local format_bitrate

    stream_bitrate="$(ffprobe -v error -select_streams a:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 "$file" | tr -d '[:space:]')"
    if [[ "$stream_bitrate" =~ ^[0-9]+$ ]] && (( stream_bitrate > 0 )); then
        echo "$stream_bitrate"
        return
    fi

    format_bitrate="$(ffprobe -v error -show_entries format=bit_rate -of default=noprint_wrappers=1:nokey=1 "$file" | tr -d '[:space:]')"
    if [[ "$format_bitrate" =~ ^[0-9]+$ ]] && (( format_bitrate > 0 )); then
        echo "$format_bitrate"
        return
    fi

    echo "0"
}

echo "[1/4] Checking ffmpeg and ffprobe..."
ensure_ffmpeg
echo ""

echo "[2/4] Scanning for supported files larger than 100MB..."
found_any=0

shopt -s nullglob
for file in *; do
    [[ -f "$file" ]] || continue

    lower_name="$(echo "$file" | tr '[:upper:]' '[:lower:]')"
    if [[ ! "$lower_name" =~ $AUDIO_REGEX ]] && [[ ! "$lower_name" =~ $VIDEO_REGEX ]]; then
        continue
    fi

    # stat -c%s is Linux-specific (unlike -f%z on macOS)
    size_bytes=$(stat -c%s "$file" 2>/dev/null || stat --format=%s "$file" 2>/dev/null)
    if [[ -z "$size_bytes" ]]; then
        continue
    fi
    if (( size_bytes <= SOURCE_MIN_BYTES )); then
        continue
    fi

    found_any=1
    ext="${file##*.}"
    ext_lower="$(echo "$ext" | tr '[:upper:]' '[:lower:]')"
    base="${file%.*}"

    if [[ "$ext_lower" == "mp4" ]]; then
        segment_seconds=$(( (TARGET_CHUNK_BYTES * 8 * 98 / 100) / MP4_OUTPUT_BITRATE_BPS ))
        if (( segment_seconds < 1 )); then
            segment_seconds=1
        fi

        rm -f "${base}_part_"*.mp3
        echo "[3/4] Extracting audio and splitting '$file' into MP3 ~50MB parts..."
        ffmpeg -hide_banner -loglevel error -i "$file" -vn -map 0:a:0 \
            -f segment -segment_time "$segment_seconds" -reset_timestamps 1 \
            -c:a libmp3lame -b:a 192k "${base}_part_%03d.mp3" \
            || { echo "Failed to process '$file'"; continue; }
    else
        bitrate_bps="$(get_bitrate_bps "$file")"
        if [[ "$bitrate_bps" == "0" ]]; then
            bitrate_bps=128000
        fi

        segment_seconds=$(( (TARGET_CHUNK_BYTES * 8 * 98 / 100) / bitrate_bps ))
        if (( segment_seconds < 1 )); then
            segment_seconds=1
        fi

        rm -f "${base}_part_"*."${ext}"
        echo "[3/4] Splitting '$file' into ~50MB parts..."
        ffmpeg -hide_banner -loglevel error -i "$file" \
            -f segment -segment_time "$segment_seconds" -reset_timestamps 1 \
            -c copy "${base}_part_%03d.${ext}" \
            || { echo "Failed to split '$file'"; continue; }
    fi
done

if (( found_any == 0 )); then
    echo "No supported files larger than 100MB were found."
    read -r -p "Press Enter to close..."
    exit 0
fi

echo ""
echo "[4/4] Completed. All eligible files processed."
read -r -p "Press Enter to close..."
