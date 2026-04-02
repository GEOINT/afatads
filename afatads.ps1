# AFATADS CLI wrapper for Windows (PowerShell)
# Ensure we can find the source code without installation
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = "$env:PYTHONPATH;$SCRIPT_DIR\src"
python -m afatads @args
