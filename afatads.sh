#!/bin/bash
# AFATADS CLI wrapper for Linux
# Ensure we can find the source code without installation
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
export PYTHONPATH="${PYTHONPATH}:${SCRIPT_DIR}/src"
python3 -m afatads "$@"
