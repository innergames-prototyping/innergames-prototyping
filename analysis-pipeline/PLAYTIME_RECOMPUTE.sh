#!/bin/sh
# macOS / Linux:  sh PLAYTIME_RECOMPUTE.sh  [run number, name or folder]
# Same as: python3 kit.py recompute
cd "$(dirname "$0")" || exit 1
PY=$(command -v python3 || command -v python) || { echo "Python 3 not found. macOS: run  xcode-select --install  once. Linux: install python3."; exit 1; }
exec "$PY" kit.py recompute "$@"
