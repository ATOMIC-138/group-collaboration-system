@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
if exist "C:\Program Files\Python39\python.exe" (
    "C:\Program Files\Python39\python.exe" "%SCRIPT_DIR%groupctl.py" %*
) else (
    python "%SCRIPT_DIR%groupctl.py" %*
)
exit /b %ERRORLEVEL%
