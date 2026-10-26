@echo off
cd /d %~dp0
set PYEXE=C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe
echo [1/3] py_compile gate...
"%PYEXE%" -m py_compile auto_runner.py
if errorlevel 1 (echo COMPILE FAILED - no build & exit /b 1)
echo [2/3] offline vtests...
"%PYEXE%" runs\_vtests\test_v2.py
if errorlevel 1 (echo VTESTS FAILED - no build & exit /b 1)
echo [3/3] PyInstaller build...
"%PYEXE%" -m PyInstaller --onefile --console --clean --name AutoWork auto_runner.py
if errorlevel 1 (echo BUILD FAILED & exit /b 1)
echo build finished OK
