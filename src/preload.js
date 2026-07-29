const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("api", {
    // File selection
    selectFiles: () => ipcRenderer.invoke("select-files"),
    selectOutputDir: () => ipcRenderer.invoke("select-output-dir"),
    getDefaultOutputDir: () => ipcRenderer.invoke("get-default-output-dir"),

    // Processing
    startProcessing: (job) => ipcRenderer.invoke("start-processing", job),
    getBitrate: (filePath) => ipcRenderer.invoke("get-bitrate", filePath),

    // Progress / log events
    onProgress: (callback) => {
        ipcRenderer.on("processing-progress", (_event, data) => callback(data));
    },
    onLog: (callback) => {
        ipcRenderer.on("processing-log", (_event, text) => callback(text));
    },
});
