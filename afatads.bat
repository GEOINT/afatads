@echo off
REM AFATADS CLI wrapper for Windows (Command Prompt)
setlocal
set "SCRIPT_DIR=%~dp0"
set "PYTHONPATH=%PYTHONPATH%;%SCRIPT_DIR%src"
python -m afatads %*
endlocal
