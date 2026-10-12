@echo off
rem 三层记忆辅导台 · 一键重启 (由 重启客户端.vbs 隐藏调用)
rem 杀残留旧窗口(本目录的 electron) + 旧后端(8766) → 干净启动
set ELECTRON_RUN_AS_NODE=
cd /d "%~dp0"
taskkill /F /IM electron.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8766 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
timeout /t 1 /nobreak >nul
"%~dp0node_modules\electron\dist\electron.exe" .
