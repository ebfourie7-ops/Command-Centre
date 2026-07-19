#!/usr/bin/env bash
set -euo pipefail

rm -f "$HOME/.local/bin/command-pdf"
rm -f "$HOME/.local/share/applications/org.commandos.PDF.desktop"
rm -f "$HOME/.local/share/icons/hicolor/1024x1024/apps/org.commandos.PDF.png"
rm -rf "$HOME/.local/share/command-pdf"
command -v update-desktop-database >/dev/null && update-desktop-database "$HOME/.local/share/applications" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
echo "Command PDF removed from this user account."
