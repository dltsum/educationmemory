@echo off
rem 三层记忆辅导台 · Electron 桌面客户端启动器
rem (本机全局设了 ELECTRON_RUN_AS_NODE=1, 会导致 Electron 退化为 node, 必须清掉)
set ELECTRON_RUN_AS_NODE=
cd /d "%~dp0"
start "" node_modules\electron\dist\electron.exe .
