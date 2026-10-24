' Watchdog bot voto: avvia e riavvia se crasha.
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
ScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = "pythonw.exe " & Chr(34) & ScriptDir & "\\bot.py" & Chr(34)
Do
  WshShell.Run cmd, 0, True
  WScript.Sleep 10000
Loop
