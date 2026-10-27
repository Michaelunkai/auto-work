@echo off
rem AutoWork campaign guard: keeps the forever campaign alive through crashes,
rem console closes, and machine hiccups. Between restarts it releases any
rem half-open completion gate left behind by the killed run, so the next
rem doctor selftest never bricks on a fresh-but-orphaned gate.
setlocal
cd /d %~dp0
set PY3=C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe
set LOG=runs\guard.log
echo [%date% %time%] guard starting >> %LOG%
:loop
AutoWork.exe forever >> %LOG% 2>&1
echo [%date% %time%] AutoWork exited with %errorlevel% - releasing gate, restart in 20s >> %LOG%
"%PY3%" -c "import json,datetime;p=r'F:\backup\ai\work-skill\state\gate\codex-work-completion-gate\active-run.json';g=json.load(open(p,encoding='utf-8-sig'));g['active']=False;g['releasedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat();g['releaseReason']='guard-restart-after-exit';json.dump(g,open(p,'w',encoding='utf-8'));print('gate released by guard')" >> %LOG% 2>&1
timeout /t 20 /nobreak >nul
goto loop
