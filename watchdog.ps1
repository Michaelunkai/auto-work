# AutoWork watchdog - keeps the guard+campaign alive forever, independent of any session.
# v2 (2026-10-29): NO CIM/Get-CimInstance (it hung machine-wide after 13:54 and a hung
# instance held the global mutex through a 7-minute outage). Liveness signals instead:
#   1. runs\guard.stop present = intentional stop -> never restart.
#   2. Newest runs\auto-*\auto-run.log modified <10 min = campaign alive -> exit.
#      (The campaign writes this log every few seconds while cycling rounds; process
#      visibility is unreliable across schtask sessions, log freshness is not.)
#   3. Log stale = campaign dead -> kill any AutoWork.exe (tasklist+taskkill only),
#      then start a fresh guard (prevents double campaigns).
# Single-instance via a global mutex so overlapping triggers can never double-start.
$ErrorActionPreference = 'SilentlyContinue'
$aw = 'F:\study\projects\career\job_search\outreach\email\gmail\windows\auto-work'
$log = Join-Path $aw 'runs\guard.log'
$stamp = Get-Date -Format 'MM-dd HH:mm:ss'

$mtx = New-Object System.Threading.Mutex($false, 'Global\AutoWorkWatchdog')
if (-not $mtx.WaitOne(0)) { exit 0 }
try {
    if (Test-Path (Join-Path $aw 'runs\guard.stop')) { exit 0 }
    $newestRun = Get-ChildItem -Path (Join-Path $aw 'runs') -Filter 'auto-run.log' -Recurse -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($newestRun -and ((Get-Date) - $newestRun.LastWriteTime).TotalMinutes -lt 10) { exit 0 }
    $orphans = & tasklist.exe /FI "IMAGENAME eq AutoWork.exe" 2>$null
    if ($orphans -match 'AutoWork\.exe') {
        & taskkill.exe /F /IM AutoWork.exe 2>$null | Out-Null
        Add-Content -Path $log -Value "[$stamp] watchdog v2: stale-log orphan AutoWork killed (no fresh run log <10 min)"
        Start-Sleep -Seconds 3
    }
    Start-Process -FilePath 'pythonw' -ArgumentList 'guard.py' -WorkingDirectory $aw -WindowStyle Hidden
    Add-Content -Path $log -Value "[$stamp] watchdog v2: guard (re)started (run log was stale >10 min)"
} finally { $mtx.ReleaseMutex() | Out-Null }
