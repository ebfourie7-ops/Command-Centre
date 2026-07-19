#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/share/command-pdf"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/1024x1024/apps"

mkdir -p "$INSTALL_DIR/assets" "$BIN_DIR" "$APP_DIR" "$ICON_DIR"
install -m 755 "$ROOT_DIR/app/command_pdf.py" "$INSTALL_DIR/command_pdf.py"
install -m 755 "$ROOT_DIR/app/start.sh" "$INSTALL_DIR/start.sh"
install -m 644 "$ROOT_DIR/app/assets/command-pdf.png" "$INSTALL_DIR/assets/command-pdf.png"
install -m 644 "$ROOT_DIR/app/README.md" "$INSTALL_DIR/README.md"

python -m venv --system-site-packages "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/python" -m pip install --upgrade pymupdf python-docx

ln -sfn "$INSTALL_DIR/start.sh" "$BIN_DIR/command-pdf"
install -m 644 "$ROOT_DIR/org.commandos.PDF.desktop" "$APP_DIR/org.commandos.PDF.desktop"
install -m 644 "$ROOT_DIR/app/assets/command-pdf.png" "$ICON_DIR/org.commandos.PDF.png"

command -v update-desktop-database >/dev/null && update-desktop-database "$APP_DIR" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
echo "Command PDF installed for $USER."
