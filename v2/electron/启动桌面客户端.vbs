' 三层记忆辅导台 · 免窗口启动器（双击即用，不弹 cmd 黑窗）
' 原理：wscript 以隐藏方式(0)拉起 electron；同时清掉本机全局的 ELECTRON_RUN_AS_NODE
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")
sh.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)
sh.Run "cmd /c set ELECTRON_RUN_AS_NODE=&& node_modules\electron\dist\electron.exe .", 0, False
