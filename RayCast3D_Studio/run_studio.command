#!/usr/bin/env bash
# RayCast3D Studio Launcher for macOS (double-click to run)
# Dependencies install automatically on first launch.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if command -v python3 &>/dev/null; then
    python3 "$SCRIPT_DIR/RayCast3D_Studio.py"
elif command -v python &>/dev/null; then
    python "$SCRIPT_DIR/RayCast3D_Studio.py"
else
    echo "ERROR: Python not found. Please install Python 3:"
    echo "  brew install python3"
    echo "  or download from https://www.python.org/downloads/"
    read -p "Press Enter to close..."
    exit 1
fi
