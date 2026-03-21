#!/usr/bin/env bash
# RayCast3D Studio Launcher for macOS/Linux
# Finds Python and runs the studio - dependencies install automatically.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Try python3 first (preferred on macOS/Linux), then python
if command -v python3 &>/dev/null; then
    python3 "$SCRIPT_DIR/RayCast3D_Studio.py"
elif command -v python &>/dev/null; then
    python "$SCRIPT_DIR/RayCast3D_Studio.py"
else
    echo "ERROR: Python not found. Please install Python 3:"
    echo "  macOS:  brew install python3"
    echo "  Ubuntu: sudo apt install python3 python3-pip python3-tk"
    exit 1
fi
