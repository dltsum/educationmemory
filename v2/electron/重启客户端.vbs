' 三层记忆辅导台 · 一键重启（双击即用，不弹 cmd 黑窗）
' 自动杀掉残留的旧后端(8766)和旧窗口，再干净启动客户端
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.Run """" & dir & "\重启客户端.bat""", 0, False
