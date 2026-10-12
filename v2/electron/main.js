// 三层记忆辅导台 · Electron 壳
// 拉起 python 后端 (server.py sidecar) → 加载本地页面; 退出时杀后端
const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

const PORT = 8766;
const URL = `http://127.0.0.1:${PORT}/`;
let backend = null;

function startBackend() {
  const serverDir = path.join(__dirname, "..");
  backend = spawn("python", ["-u", "server.py"], { cwd: serverDir, windowsHide: true });
  backend.on("error", (e) => console.error("后端启动失败:", e));
}

function waitReady(cb, tries = 60) {
  http.get(URL, () => cb()).on("error", () => {
    if (tries <= 0) return cb(); // 兜底: 即使后端没起也开窗, 页面会提示
    setTimeout(() => waitReady(cb, tries - 1), 500);
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1360, height: 860, minWidth: 1000, minHeight: 640,
    title: "三层记忆辅导台",
    backgroundColor: "#0b0f1a",
    autoHideMenuBar: true,
  });
  win.loadURL(URL);
}

app.whenReady().then(() => {
  startBackend();
  waitReady(createWindow);
  app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

app.on("window-all-closed", () => {
  if (backend) backend.kill();
  app.quit();
});
app.on("quit", () => { if (backend) backend.kill(); });
