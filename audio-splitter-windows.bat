@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "SCRIPT_VERSION=2026.09.18"

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
echo ffmpeg/ffprobe not found. Attempting auto-install...
where winget >nul 2>nul
if not errorlevel 1 (
  winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto install_failed
  goto recheck_ffmpeg
)
where choco >nul 2>nul
if not errorlevel 1 (
  choco install ffmpeg -y
  if errorlevel 1 goto install_failed
  goto recheck_ffmpeg
)

:install_failed
echo.
echo Could not auto-install ffmpeg.
echo Please install ffmpeg manually, then run this script again.
pause
exit /b 1

:recheck_ffmpeg
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo ffmpeg is not available in the current PATH.
  echo Try opening a new Command Prompt and run this script again.
  pause
  exit /b 1
)
where ffprobe >nul 2>nul
if errorlevel 1 (
  echo ffprobe is not available in the current PATH.
  echo Try opening a new Command Prompt and run this script again.
  pause
  exit /b 1
)
goto run_split

:run_split
echo.
echo [2/4] Scanning for supported audio/video files larger than 100MB...
echo.
echo [3/4] Splitting into parts with a target size of approximately 50MB...
echo.
echo Note: output parts are kept below the 50MB target where possible.
echo Existing generated parts for the same source file will be replaced.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $sourceMin=100MB; $target=50MB; $safety=0.98; $audioExts=@('mp3','m4a','aac','wav','flac','ogg'); $videoExts=@('mp4'); $mp4OutBitrate=192000; $files=@(Get-ChildItem -Path . -File | Where-Object { $e=$_.Extension.TrimStart('.').ToLowerInvariant(); (($audioExts -contains $e) -or ($videoExts -contains $e)) -and $_.Length -gt $sourceMin }); if($files.Count -eq 0){ Write-Host 'No supported files larger than 100MB were found.' -ForegroundColor Yellow; exit 0 }; $failed=$false; foreach($f in $files){ $ext=$f.Extension.TrimStart('.').ToLowerInvariant(); $base=[System.IO.Path]::GetFileNameWithoutExtension($f.Name); $safeBase=[regex]::Escape($base); if($ext -eq 'mp4'){ $seg=[math]::Floor(($target*8*$safety)/$mp4OutBitrate); if($seg -lt 1){$seg=1}; Get-ChildItem -Path . -File | Where-Object { $_.Name -match ('^'+$safeBase+'_part_[0-9]+.mp3$') } | Remove-Item -Force -ErrorAction SilentlyContinue; $pattern=Join-Path (Get-Location) ($base+'_part_%03d.mp3'); Write-Host ('Extracting audio and splitting '''+$f.Name+''' to MP3 parts...') -ForegroundColor Green; & ffmpeg -hide_banner -loglevel error -y -i $f.FullName -vn -map 0:a:0 -f segment -segment_time $seg -reset_timestamps 1 -c:a libmp3lame -b:a 192k $pattern } else { $stream=(& ffprobe -v error -select_streams a:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 $f.FullName 2>$null).Trim(); if(-not ($stream -match '^d+$') -or [int64]$stream -le 0){$stream=(& ffprobe -v error -show_entries format=bit_rate -of default=noprint_wrappers=1:nokey=1 $f.FullName 2>$null).Trim()}; if(-not ($stream -match '^d+$') -or [int64]$stream -le 0){$stream='128000'}; $seg=[math]::Floor(($target*8*$safety)/[int64]$stream); if($seg -lt 1){$seg=1}; $pattern=Join-Path (Get-Location) ($base+'_part_%03d.'+$ext); Get-ChildItem -Path . -File | Where-Object { $_.Name -match ('^'+$safeBase+'_part_[0-9]+.'+[regex]::Escape($ext)+'$') } | Remove-Item -Force -ErrorAction SilentlyContinue; Write-Host ('Splitting '''+$f.Name+'''...') -ForegroundColor Green; & ffmpeg -hide_banner -loglevel error -y -i $f.FullName -f segment -segment_time $seg -reset_timestamps 1 -c copy $pattern }; $exitCode=$LASTEXITCODE; if($exitCode -ne 0){ Write-Warning ('Failed: '+$f.Name+' (ffmpeg exit code '+$exitCode+')'); $failed=$true; continue }; $parts=@(Get-ChildItem -Path . -File | Where-Object { $_.Name -match ('^'+$safeBase+'_part_[0-9]+.'+$(if($ext -eq 'mp4'){'mp3'}else{[regex]::Escape($ext)})+'$') }); if($parts.Count -eq 0){ Write-Warning ('Failed: no output parts were created for '+$f.Name); $failed=$true; continue }; $oversized=@($parts | Where-Object { $_.Length -gt $target }); if($oversized.Count -gt 0){ Write-Warning ('Warning: '+$oversized.Count+' part(s) exceeded 50MB for '+$f.Name+' because the source codec was copied without re-encoding.'); $failed=$true } else { Write-Host ('Done: '+$f.Name+' - '+$parts.Count+' part(s) created.') -ForegroundColor Cyan } }; if($failed){ Write-Warning 'One or more files failed or produced parts above the 50MB target.'; exit 1 }; exit 0"

if errorlevel 1 (
  echo.
  echo Split process failed or one or more files require attention.
  pause
  exit /b 1
)

echo.
echo [4/4] Completed.
echo All eligible supported files have been processed successfully.
pause
exit /b 0
