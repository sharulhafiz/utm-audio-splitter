@echo off
setlocal EnableExtensions EnableDelayedExpansion

set SCRIPT_VERSION=2026.03.04

title Audio Splitter (Windows)
cd /d "%~dp0"

echo ============================================
echo   Audio Splitter - Windows
echo   Version: %SCRIPT_VERSION%

echo   Folder: %cd%
echo ============================================

echo.
echo [1/4] Checking ffmpeg and ffprobe...
where ffmpeg >nul 2>nul
if errorlevel 1 goto install_ffmpeg
where ffprobe >nul 2>nul
if errorlevel 1 goto install_ffmpeg
goto run_split

:install_ffmpeg
echo ffmpeg not found. Attempting auto-install...
where winget >nul 2>nul
if not errorlevel 1 (
  winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
  goto recheck_ffmpeg
)
where choco >nul 2>nul
if not errorlevel 1 (
  choco install ffmpeg -y
  goto recheck_ffmpeg
)

echo Could not auto-install ffmpeg.
echo Please install ffmpeg manually, then run this script again.
pause
exit /b 1

:recheck_ffmpeg
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo ffmpeg still not available. Try opening a new Command Prompt and run again.
  pause
  exit /b 1
)
where ffprobe >nul 2>nul
if errorlevel 1 (
  echo ffprobe still not available. Try opening a new Command Prompt and run again.
  pause
  exit /b 1
)

:run_split
echo.
echo [2/4] Scanning for supported audio/video files larger than 100MB...

echo.
echo [3/4] Splitting into ~50MB parts in the same folder...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $sourceMin=100MB; $target=50MB; $audioExts=@('mp3','m4a','aac','wav','flac','ogg'); $videoExts=@('mp4'); $mp4OutBitrate=192000; $files=Get-ChildItem -Path . -File | Where-Object { $e=$_.Extension.TrimStart('.').ToLower(); (($audioExts -contains $e) -or ($videoExts -contains $e)) -and $_.Length -gt $sourceMin }; if(-not $files){ Write-Host 'No supported files larger than 100MB were found.' -ForegroundColor Yellow; exit 0 }; foreach($f in $files){ $ext=$f.Extension.TrimStart('.').ToLower(); $base=[System.IO.Path]::GetFileNameWithoutExtension($f.Name); if($ext -eq 'mp4'){ $seg=[math]::Floor(($target*8)/$mp4OutBitrate); if($seg -lt 1){ $seg=1 }; Get-ChildItem -Path . -File -Filter \"${base}_part_*.mp3\" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue; $pattern=Join-Path (Get-Location) \"${base}_part_%%03d.mp3\"; Write-Host \"Extracting audio and splitting '$($f.Name)' to MP3 parts...\" -ForegroundColor Green; & ffmpeg -hide_banner -loglevel error -i \"$($f.FullName)\" -vn -map 0:a:0 -f segment -segment_time $seg -reset_timestamps 1 -c:a libmp3lame -b:a 192k \"$pattern\" } else { $stream=(& ffprobe -v error -select_streams a:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 \"$($f.FullName)\").Trim(); if(-not ($stream -match '^\d+$') -or [int64]$stream -le 0){ $stream=(& ffprobe -v error -show_entries format=bit_rate -of default=noprint_wrappers=1:nokey=1 \"$($f.FullName)\").Trim() }; if(-not ($stream -match '^\d+$') -or [int64]$stream -le 0){ $stream='128000' }; $seg=[math]::Floor(($target*8)/[int64]$stream); if($seg -lt 1){ $seg=1 }; Get-ChildItem -Path . -File -Filter \"${base}_part_*.${ext}\" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue; $pattern=Join-Path (Get-Location) \"${base}_part_%%03d.${ext}\"; Write-Host \"Splitting '$($f.Name)'...\" -ForegroundColor Green; & ffmpeg -hide_banner -loglevel error -i \"$($f.FullName)\" -f segment -segment_time $seg -reset_timestamps 1 -c copy \"$pattern\" }; if($LASTEXITCODE -ne 0){ Write-Warning \"Failed: $($f.Name)\" } else { Write-Host \"Done: $($f.Name)\" -ForegroundColor Cyan } }"
if errorlevel 1 (
  echo.
  echo Split process failed.
  pause
  exit /b 1
)

echo.
echo [4/4] Completed.
echo All eligible supported files have been processed.
pause
exit /b 0
