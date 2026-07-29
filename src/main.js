const {
    app, BrowserWindow, ipcMain, dialog,
} = require("electron");
const path = require("path");
const { spawn, execSync } = require("child_process");
const fs = require("fs");

// ── FFmpeg binary paths (bundled via ffmpeg-static / ffprobe-static) ──────────
let ffmpegPath = null;
let ffprobePath = null;

function resolveBin(pkgBase, binName) {
    // In dev: node_modules/<pkg>/<bin>
    // In production: <resources>/<pkg>/<bin>
    const candidates = [
        path.join(__dirname, "..", "node_modules", pkgBase, binName),
        path.join(process.resourcesPath || "", pkgBase, binName),
        path.join(process.resourcesPath || "", pkgBase, "index.js"),    // some wrappers
    ];
    for (const c of candidates) {
        try {
            if (fs.statSync(c).isFile()) {
                // If it's a JS wrapper, read the actual binary path
                if (c.endsWith(".js")) {
                    const mod = require(c);
                    if (typeof mod === "string") return mod;
                    if (mod.path) return mod.path;
                    continue;
                }
                return c;
            }
        } catch (_) { /* not found */ }
    }
    // Final fallback: just `ffmpeg` on PATH
    return binName;
}

function initFFmpeg() {
    // In production (packaged app), binaries live in extraResources outside asar
    // Try them first since asar paths can't be executed.
    const isPackaged = app.isPackaged;
    const binName = process.platform === "win32" ? "ffmpeg.exe" : "ffmpeg";
    const probeName = process.platform === "win32" ? "ffprobe.exe" : "ffprobe";

    if (isPackaged && process.resourcesPath) {
        const ffCandidate = path.join(process.resourcesPath, "ffmpeg-static", binName);
        const fpCandidate = path.join(process.resourcesPath, "ffprobe-static", probeName);
        if (fs.existsSync(ffCandidate)) ffmpegPath = ffCandidate;
        if (fs.existsSync(fpCandidate)) ffprobePath = fpCandidate;
    }

    // Fallback: require() for development or as fallback
    if (!ffmpegPath) {
        try {
            const ffstatic = require("ffmpeg-static");
            const raw = typeof ffstatic === "string" ? ffstatic : ffstatic.path;
            // Only use if it's not inside an asar archive
            if (raw && !raw.includes(".asar")) ffmpegPath = raw;
        } catch { /* ignore */ }
    }
    if (!ffmpegPath) {
        ffmpegPath = resolveBin("ffmpeg-static", binName);
    }

    if (!ffprobePath) {
        try {
            const fpstatic = require("ffprobe-static");
            const raw = typeof fpstatic === "string" ? fpstatic : fpstatic.path;
            if (raw && !raw.includes(".asar")) ffprobePath = raw;
        } catch { /* ignore */ }
    }
    if (!ffprobePath) {
        ffprobePath = resolveBin("ffprobe-static", probeName);
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function getBitrate(filePath) {
    return new Promise((resolve) => {
        const cmd = `"${ffprobePath}" -v error -select_streams a:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 "${filePath}"`;
        execSync(cmd, { timeout: 15000 }).toString().trim();
    }).then(r => parseInt(r, 10)).catch(() => 0);
}

function getDuration(filePath) {
    try {
        const out = execSync(
            `"${ffprobePath}" -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "${filePath}"`,
            { timeout: 15000 }
        ).toString().trim();
        return parseFloat(out) || 0;
    } catch { return 0; }
}

// ── IPC handlers ──────────────────────────────────────────────────────────────

ipcMain.handle("select-files", async () => {
    const result = await dialog.showOpenDialog({
        properties: ["openFile", "multiSelections"],
        filters: [{
            name: "Audio / Video",
            extensions: ["mp3", "m4a", "aac", "wav", "flac", "ogg", "mp4", "mkv", "mov", "avi", "webm"],
        }],
    });
    return result.filePaths || [];
});

ipcMain.handle("select-output-dir", async () => {
    const result = await dialog.showOpenDialog({
        properties: ["openDirectory"],
    });
    return result.filePaths[0] || "";
});

ipcMain.handle("get-bitrate", async (_event, filePath) => {
    try {
        const out = execSync(
            `"${ffprobePath}" -v error -select_streams a:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 "${filePath}"`,
            { timeout: 15000 }
        ).toString().trim();
        const br = parseInt(out, 10);
        if (!isNaN(br) && br > 0) return br;
        const out2 = execSync(
            `"${ffprobePath}" -v error -show_entries format=bit_rate -of default=noprint_wrappers=1:nokey=1 "${filePath}"`,
            { timeout: 15000 }
        ).toString().trim();
        return parseInt(out2, 10) || 128000;
    } catch { return 128000; }
});

ipcMain.handle("get-default-output-dir", async () => {
    const home = app.getPath("home");
    return path.join(home, "Desktop", "SplitAudio");
});

ipcMain.handle("start-processing", async (event, job) => {
    // job: { inputPaths[], outputDir, mode, targetFormat, segmentSeconds, maxSizeMB }
    const results = [];
    for (let i = 0; i < job.inputPaths.length; i++) {
        const filePath = job.inputPaths[i];
        const base = path.basename(filePath, path.extname(filePath));
        const ext = path.extname(filePath).toLowerCase();
        let audioSource = filePath;
        let tempFile = null;

        event.sender.send("processing-log", `\n[${i + 1}/${job.inputPaths.length}] ${path.basename(filePath)}`);

        // ── Video → audio extraction ──
        const videoExts = [".mp4", ".mkv", ".mov", ".avi", ".webm"];
        if (videoExts.includes(ext)) {
            tempFile = path.join(job.outputDir, `__temp_${base}_${Date.now()}.wav`);
            event.sender.send("processing-log", "→ Extracting audio from video...");
            await runFFmpeg([
                ffmpegPath,
                "-hide_banner", "-loglevel", "error",
                "-i", filePath,
                "-vn", "-map", "0:a:0",
                "-acodec", "pcm_s16le",
                "-y", tempFile,
            ], event.sender, `Extracting audio: ${path.basename(filePath)}`);
            audioSource = tempFile;
            // recalc for split
            const newExt = ".wav";
            Object.assign(job, { currentExt: newExt });
            event.sender.send("processing-log", "✓ Audio extracted.");
        }

        // ── Process by mode ──
        if (job.mode === "extract") {
            const outName = `${base}.${job.targetFormat}`;
            const outPath = path.join(job.outputDir, outName);
            await runFFmpeg([
                ffmpegPath,
                "-hide_banner", "-loglevel", "error",
                "-i", audioSource,
                "-vn", "-map", "0:a:0",
                "-acodec", job.targetFormat === "mp3" ? "libmp3lame" : job.targetFormat === "wav" ? "pcm_s16le" : "aac",
                "-y", outPath,
            ], event.sender, `Converting: ${path.basename(filePath)}`);
            results.push(outPath);
        } else if (job.mode === "split_duration") {
            const seg = Math.max(1, job.segmentSeconds || 300);
            const outExt = path.extname(audioSource) || ".mp3";
            const pattern = path.join(job.outputDir, `${base}_part_%03d${outExt}`);
            cleanupParts(job.outputDir, base, outExt);
            await runFFmpeg([
                ffmpegPath,
                "-hide_banner", "-loglevel", "error",
                "-i", audioSource,
                "-f", "segment",
                "-segment_time", String(seg),
                "-reset_timestamps", "1",
                "-c", "copy",
                "-y", pattern,
            ], event.sender, `Splitting ${seg}s: ${path.basename(filePath)}`);
        } else if (job.mode === "split_size") {
            const maxBytes = (job.maxSizeMB || 25) * 1024 * 1024;
            const br = await getBitrate(audioSource);
            const bitrate = br > 0 ? br : 128000;
            const seg = Math.max(1, Math.floor((maxBytes * 8) / bitrate));
            const outExt = path.extname(audioSource) || ".mp3";
            const pattern = path.join(job.outputDir, `${base}_part_%03d${outExt}`);
            cleanupParts(job.outputDir, base, outExt);
            event.sender.send("processing-log", `→ Bitrate: ${bitrate} bps → segment ~${seg}s (max ${job.maxSizeMB}MB)`);
            await runFFmpeg([
                ffmpegPath,
                "-hide_banner", "-loglevel", "error",
                "-i", audioSource,
                "-f", "segment",
                "-segment_time", String(seg),
                "-reset_timestamps", "1",
                "-c", "copy",
                "-y", pattern,
            ], event.sender, `Splitting ≤${job.maxSizeMB}MB: ${path.basename(filePath)}`);
        }

        // Cleanup temp
        if (tempFile) {
            try { fs.unlinkSync(tempFile); } catch { /* ignore */ }
        }
    }
    return { success: true, message: "All files processed." };
});

function runFFmpeg(args, sender, label) {
    return new Promise((resolve, reject) => {
        const proc = spawn(args[0], args.slice(1));
        let duration = 0;
        const timeRe = /time=(\d+):(\d+):(\d+\.\d+)/;
        let lastPct = 0;

        // Try to detect duration from input
        try {
            const idx = args.indexOf("-i") + 1;
            if (idx > 0 && idx < args.length) {
                duration = getDuration(args[idx]);
            }
        } catch { /* ignore */ }

        sender.send("processing-progress", { pct: 0, label });

        proc.stderr.on("data", (data) => {
            const text = data.toString();
            const m = timeRe.exec(text);
            if (m) {
                const elapsed = parseInt(m[1], 10) * 3600 + parseInt(m[2], 10) * 60 + parseFloat(m[3]);
                if (duration > 0 && elapsed - lastPct >= 1) {
                    const pct = Math.min(99, Math.floor((elapsed / duration) * 100));
                    sender.send("processing-progress", { pct, label });
                    lastPct = elapsed;
                }
            }
        });

        proc.on("close", (code) => {
            if (code === 0) {
                sender.send("processing-progress", { pct: 100, label });
                resolve();
            } else {
                reject(new Error(`ffmpeg exited with code ${code}`));
            }
        });

        proc.on("error", reject);
    });
}

function cleanupParts(dir, base, ext) {
    try {
        const files = fs.readdirSync(dir);
        const re = new RegExp(`^${escapeRegex(base)}_part_\\d+${escapeRegex(ext)}$`);
        for (const f of files) {
            if (re.test(f)) {
                fs.unlinkSync(path.join(dir, f));
            }
        }
    } catch { /* ignore */ }
}

function escapeRegex(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// ── Window ────────────────────────────────────────────────────────────────────

function createWindow() {
    initFFmpeg();

    const win = new BrowserWindow({
        width: 820,
        height: 720,
        minWidth: 640,
        minHeight: 560,
        title: "UTM Audio Splitter",
        webPreferences: {
            preload: path.join(__dirname, "preload.js"),
            contextIsolation: true,
            nodeIntegration: false,
        },
    });

    win.loadFile(path.join(__dirname, "renderer", "index.html"));
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
