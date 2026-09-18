@echo off
cd /d "%~dp0"
py -3.13 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -e ".[build]"
if errorlevel 1 goto fail
.venv\Scripts\python.exe build_tools\build.py
if errorlevel 1 goto fail
echo Finished. See the dist folder.
pause
exit /b 0
:fail
echo Build failed. Please retain the output above.
pause
exit /b 1
