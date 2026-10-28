' AutoWork guard launcher - hidden, detached from any session (owned by Task Scheduler)
Dim sh: Set sh = CreateObject("Wscript.Shell")
sh.CurrentDirectory = "F:\study\projects\career\job_search\outreach\email\gmail\windows\auto-work"
sh.Run """C:\Users\Admin\AppData\Local\Programs\Python\Python312\pythonw.exe"" guard.py", 0, False
