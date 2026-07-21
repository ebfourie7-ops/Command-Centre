#!/bin/sh
set -eu
SCRIPT_PATH=$(readlink -f -- "$0" 2>/dev/null || realpath -- "$0")
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd)
if [ -x "$APP_DIR/.venv/bin/python" ]; then
    exec "$APP_DIR/.venv/bin/python" "$APP_DIR/command_pdf.py" "$@"
fi
exec python "$APP_DIR/command_pdf.py" "$@"
