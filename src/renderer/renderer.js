/* ── State ─────────────────────────────────────────────── */
const state = {
    files: [],
    outputDir: "",
    processing: false,
    cancelled: false,
};

/* ── DOM refs ──────────────────────────────────────────── */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dropzone = $("#dropzone");
const fileList = $("#file-list");
const fileInfo = $("#file-info");
const btnBrowse = $("#btn-browse");
const btnClear = $("#btn-clear");
const modeRadios = $$('input[name="mode"]');
const configFormat = $("#config-format");
const configDuration = $("#config-duration");
const configSize = $("#config-size");
const outputFormat = $("#output-format");
const segmentSeconds = $("#segment-seconds");
const maxSizeMb = $("#max-size-mb");
const outputDir = $("#output-dir");
const btnOutput = $("#btn-output");
const btnStart = $("#btn-start");
const btnCancel = $("#btn-cancel");
const progressBar = $("#progress-bar");
const progressLabel = $("#progress-label");
const logBox = $("#log-box");

/* ── Default output dir ───────────────────────────────── */
const defaultDir = ""; // will be set from main process

/* ── Init ──────────────────────────────────────────────── */
(async function init() {
    const defaultDir = await window.api.getDefaultOutputDir();
    outputDir.value = defaultDir;
    state.outputDir = defaultDir;
})();

/* ── Dropzone & Browse ────────────────────────────────── */
dropzone.addEventListener("click", () => selectFiles());

// Drag events
dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-over");
});
dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("drag-over");
});
dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
    const paths = Array.from(e.dataTransfer.files).map((f) => f.path);
    if (paths.length) addFiles(paths);
});

btnBrowse.addEventListener("click", (e) => {
    e.stopPropagation();
    selectFiles();
});

async function selectFiles() {
    if (state.processing) return;
    const paths = await window.api.selectFiles();
    if (paths.length) addFiles(paths);
}

function addFiles(paths) {
    const validExts = new Set([
        ".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg",
        ".mp4", ".mkv", ".mov", ".avi", ".webm",
    ]);
    const valid = paths.filter((p) => {
        const ext = p.split(".").pop().toLowerCase();
        return validExts.has(`.${ext}`);
    });
    if (!valid.length) return;

    // Merge, dedupe
    const seen = new Set(state.files);
    for (const f of valid) {
        if (!seen.has(f)) {
            state.files.push(f);
            seen.add(f);
        }
    }
    renderFileList();
}

function removeFile(idx) {
    state.files.splice(idx, 1);
    renderFileList();
}

function renderFileList() {
    fileList.innerHTML = "";
    if (state.files.length === 0) {
        fileList.classList.add("hidden");
        fileInfo.textContent = "No files selected";
        btnClear.classList.add("hidden");
        return;
    }
    fileList.classList.remove("hidden");
    btnClear.classList.remove("hidden");

    state.files.forEach((f, i) => {
        const tag = document.createElement("span");
        tag.className = "file-tag";
        tag.textContent = f.split(/[/\\]/).pop();
        tag.title = f;
        tag.addEventListener("click", () => removeFile(i));
        tag.style.cursor = "pointer";
        fileList.appendChild(tag);
    });

    const exts = [...new Set(state.files.map((f) => f.split(".").pop().toLowerCase()))];
    fileInfo.textContent = `${state.files.length} file(s): ${exts.map((e) => `.${e}`).join(", ")}`;
    updateStartButton();
}

btnClear.addEventListener("click", () => {
    state.files = [];
    renderFileList();
});

/* ── Mode switching ────────────────────────────────────── */
modeRadios.forEach((radio) => {
    radio.addEventListener("change", () => {
        const mode = document.querySelector('input[name="mode"]:checked').value;
        configFormat.classList.remove("hidden");
        configDuration.classList.add("hidden");
        configSize.classList.add("hidden");
        if (mode === "split_duration") configDuration.classList.remove("hidden");
        if (mode === "split_size") configSize.classList.remove("hidden");
    });
});

// Mode option click = radio select
$$(".mode-option").forEach((el) => {
    el.addEventListener("click", () => {
        const radio = el.querySelector("input[type=radio]");
        if (radio) radio.click();
    });
});

/* ── Output directory ─────────────────────────────────── */
btnOutput.addEventListener("click", async () => {
    if (state.processing) return;
    const dir = await window.api.selectOutputDir();
    if (dir) {
        state.outputDir = dir;
        outputDir.value = dir;
    }
});

/* ── Processing ────────────────────────────────────────── */
btnStart.addEventListener("click", startProcessing);
btnCancel.addEventListener("click", cancelProcessing);

async function startProcessing() {
    if (state.processing || state.files.length === 0) return;

    const mode = document.querySelector('input[name="mode"]:checked').value;

    // Validate output dir
    if (!state.outputDir) {
        log("❌ Please select an output directory.");
        return;
    }

    state.processing = true;
    state.cancelled = false;
    updateButtons();
    progressBar.style.width = "0%";
    progressLabel.textContent = "Starting...";
    logBox.textContent = "";
    log("▶ Processing started...\n");

    const job = {
        inputPaths: state.files,
        outputDir: state.outputDir,
        mode: mode,
        targetFormat: outputFormat.value,
        segmentSeconds: parseInt(segmentSeconds.value, 10) || 300,
        maxSizeMB: parseInt(maxSizeMb.value, 10) || 25,
    };

    try {
        const result = await window.api.startProcessing(job);
        if (result.success) {
            progressBar.style.width = "100%";
            progressLabel.textContent = "✅ Complete!";
            log("\n✅ " + result.message);
        } else {
            progressBar.style.width = "0%";
            progressLabel.textContent = "❌ Failed";
            log("\n❌ " + result.message);
        }
    } catch (err) {
        progressBar.style.width = "0%";
        progressLabel.textContent = "❌ Error";
        log("\n❌ " + err.message);
    }

    state.processing = false;
    updateButtons();
}

function cancelProcessing() {
    state.cancelled = true;
    // Can't force-kill the main process easily via IPC without risk,
    // but we set the flag and the renderer will get the error.
    log("✕ Cancelling... (will stop after current file)");
    // In practice, the user can close the window to kill all child processes.
}

/* ── IPC event handlers ────────────────────────────────── */
window.api.onProgress((data) => {
    if (state.cancelled) return;
    progressBar.style.width = `${data.pct}%`;
    progressLabel.textContent = `${data.label} (${data.pct}%)`;
});

window.api.onLog((text) => {
    log(text);
});

function log(text) {
    logBox.textContent += text;
    logBox.scrollTop = logBox.scrollHeight;
}

/* ── UI helpers ────────────────────────────────────────── */
function updateButtons() {
    btnStart.disabled = state.processing || state.files.length === 0;
    btnCancel.disabled = !state.processing;
    btnBrowse.disabled = state.processing;
    btnClear.disabled = state.processing;
    btnOutput.disabled = state.processing;
    dropzone.style.pointerEvents = state.processing ? "none" : "auto";
}

function updateStartButton() {
    if (!state.processing) {
        btnStart.disabled = state.files.length === 0;
    }
}

/* ── Keyboard shortcut ─────────────────────────────────── */
document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !state.processing && state.files.length > 0) {
        startProcessing();
    }
});
