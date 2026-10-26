@echo off
setlocal
title AutoWork v2.0.0 - one batch (find + send)
set WORK_BACKUP_ROOT=F:\backup\ai\work-skill
set WORK_PROJECT=F:\study\projects\career\job_search\outreach\email\gmail\windows\job-application-email-sender
set AWDIR=F:\study\projects\career\job_search\outreach\email\gmail\windows\auto-work
set PY3=C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe
if not exist %AWDIR%\AutoWork.exe goto py
"%AWDIR%\AutoWork.exe" %*
goto end
:py
"%PY3%" "%AWDIR%\auto_runner.py" %*
:end
echo.
pause
