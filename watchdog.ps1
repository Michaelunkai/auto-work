# AutoWork watchdog - keeps the guard+campaign alive forever, independent of any session.
# Rules (mirrors the documented manual recovery procedure):
#   1. runs\guard.stop present = intentional stop -> never restart.
#   2. A pythonw running guard.py = healthy -> exit.
#   3. Guard dead + AutoWork orphan(s) alive -> tree-kill orphans first (taskkill /F /T),
#      then start a fresh guard (prevents double campaigns).
#   4. Guard dead + no AutoWork -> start a fresh guard.
# Single-instance via a global mutex so overlapping triggers can never double-start.
$ErrorActionPreference = 'SilentlyContinue'
$aw = 'F:\study\projects\career\job_search\outreach\email\gmail\windows\auto-work'
$log = Join-Path $aw 'runs\guard.log'
$stamp = Get-Date -Format 'MM-dd HH:mm:ss'

$mtx = New-Object System.Threading.Mutex($false, 'Global\AutoWorkWatchdog')
if (-not $mtx.WaitOne(0)) { exit 0 }
try {
    if (Test-Path (Join-Path $aw 'runs\guard.stop')) { exit 0 }
    $guard = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like '*guard.py*' }
    if ($guard) { exit 0 }
    $orphans = Get-Process -Name 'AutoWork' -ErrorAction SilentlyContinue
    if ($orphans) {
        foreach ($p in $orphans) { & taskkill.exe /F /T /PID $p.Id | Out-Null }
        Add-Content -Path $log -Value "[$stamp] watchdog: orphan AutoWork tree killed (guard was dead)"
        Start-Sleep -Seconds 3
    }
    Start-Process -FilePath 'pythonw' -ArgumentList 'guard.py' -WorkingDirectory $aw -WindowStyle Hidden
    Add-Content -Path $log -Value "[$stamp] watchdog: guard (re)started"
} finally { $mtx.ReleaseMutex() | Out-Null }
