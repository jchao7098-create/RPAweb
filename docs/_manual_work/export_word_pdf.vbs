Option Explicit

Dim inputPath, outputPath, wordApp, document
inputPath = WScript.Arguments(0)
outputPath = WScript.Arguments(1)

Set wordApp = CreateObject("Word.Application")
wordApp.Visible = False
wordApp.DisplayAlerts = 0

On Error Resume Next
Set document = wordApp.Documents.Open(inputPath, False, True, False)
If Err.Number <> 0 Then
  WScript.Echo "OPEN_ERROR " & Err.Number & " " & Err.Description
  wordApp.Quit
  WScript.Quit 2
End If

Err.Clear
document.ExportAsFixedFormat outputPath, 17, False, 0, 0, 1, 9999, 0, True, True, 1, True, True, False
If Err.Number <> 0 Then
  WScript.Echo "EXPORT_ERROR " & Err.Number & " " & Err.Description
  document.Close False
  wordApp.Quit
  WScript.Quit 3
End If

document.Close False
wordApp.Quit
WScript.Echo "EXPORTED " & outputPath
