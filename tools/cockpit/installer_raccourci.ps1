# Cree l'icone "Cockpit Anthropos" sur le Bureau (une fois). ASCII pur.
$ErrorActionPreference = "Stop"
$Lanceur = Join-Path $PSScriptRoot "lancer.ps1"
$Bureau  = [Environment]::GetFolderPath("Desktop")
$Lnk     = Join-Path $Bureau "Cockpit Anthropos.lnk"
$Shell = New-Object -ComObject WScript.Shell
$S = $Shell.CreateShortcut($Lnk)
$S.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$S.Arguments  = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Lanceur`""
$S.WorkingDirectory = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$S.Description = "Cockpit Anthropos (poste)"
$S.IconLocation = "$env:SystemRoot\System32\shell32.dll,43"
$S.Save()
Write-Output "Raccourci cree : $Lnk"
