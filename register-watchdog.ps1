# Registers the AutoWork watchdog scheduled task (logon + every 5 minutes).
$ErrorActionPreference = 'Stop'
$aw = 'F:\study\projects\career\job_search\outreach\email\gmail\windows\auto-work'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ("-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"" + $aw + "\watchdog.ps1`"")
$tLogon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$tRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
try {
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited
    Register-ScheduledTask -TaskName 'AutoWork-Watchdog' -Action $action -Trigger @($tLogon, $tRepeat) -Settings $settings -Principal $principal -Force | Out-Null
    Write-Output 'REGISTERED with S4U principal (runs even before logon)'
} catch {
    Write-Output ("S4U failed (" + $_.Exception.Message + ") - retrying Interactive")
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName 'AutoWork-Watchdog' -Action $action -Trigger @($tLogon, $tRepeat) -Settings $settings -Principal $principal -Force | Out-Null
    Write-Output 'REGISTERED with Interactive principal'
}
(Get-ScheduledTask -TaskName 'AutoWork-Watchdog').State
