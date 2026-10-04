# Cockpit Anthropos - lanceur poste. ASCII pur : PowerShell 5.1 lit un .ps1 sans BOM en ANSI.
# Port fixe : tools/cv/atelier.py appelle server.main() sans argument, donc toujours 8010.
$Port = 8010
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"   # sinon cockpit.out.log reste vide tant que le serveur tourne
$SiteRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Url = "http://127.0.0.1:$Port/"

function Test-PortOuvert([int]$p) {
    $c = New-Object System.Net.Sockets.TcpClient
    try { return ($c.ConnectAsync("127.0.0.1", $p).Wait(500) -and $c.Connected) }
    catch { return $false } finally { $c.Dispose() }
}

if (-not (Test-PortOuvert $Port)) {
    $Python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\pythonw.exe"
    if (-not (Test-Path $Python)) { $Python = (Get-Command pythonw.exe).Source }
    $LogDir = Join-Path $env:LOCALAPPDATA "Anthropos"
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    Start-Process -FilePath $Python -ArgumentList @("tools/cv/atelier.py") -WorkingDirectory $SiteRoot `
        -RedirectStandardOutput (Join-Path $LogDir "cockpit.out.log") `
        -RedirectStandardError  (Join-Path $LogDir "cockpit.err.log") -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds(15)
    while (-not (Test-PortOuvert $Port) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 250 }
    if (-not (Test-PortOuvert $Port)) { throw "Le cockpit ne repond pas sur $Port apres 15 s - voir $LogDir\cockpit.err.log" }
}
Start-Process $Url
