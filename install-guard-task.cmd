@echo off
schtasks /Create /TN AutoWorkGuard /TR "wscript.exe \"F:\study\projects\career\job_search\outreach\email\gmail\windows\auto-work\start-guard-hidden.vbs\"" /SC ONLOGON /RL LIMITED /F
schtasks /Query /TN AutoWorkGuard
