#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:-}"
TARGET_DIR="/opt/command-centre"
LAUNCHER="/usr/bin/command-centre"
DESKTOP_FILE="/usr/share/applications/command-centre.desktop"
ICON_FILE="/usr/share/icons/hicolor/512x512/apps/command-centre.png"

if [[ -z "$SOURCE_DIR" || ! -f "$SOURCE_DIR/command_centre.py" || ! -f "$SOURCE_DIR/command_intel.py" ]]; then
  echo "Refusing update: invalid Command Centre source directory." >&2
  exit 2
fi

install -d -m 755 "$TARGET_DIR" /usr/bin /usr/share/applications /usr/share/icons/hicolor/512x512/apps
find "$TARGET_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
cp -a "$SOURCE_DIR/." "$TARGET_DIR/"

install -Dm644 "$SOURCE_DIR/packaging/arch/command-centre.desktop" "$DESKTOP_FILE"
if [[ -f "$SOURCE_DIR/ChatGPT Image Jul 9, 2026, 09_59_59 PM.png" ]]; then
  install -Dm644 "$SOURCE_DIR/ChatGPT Image Jul 9, 2026, 09_59_59 PM.png" "$TARGET_DIR/logo.png"
  install -Dm644 "$SOURCE_DIR/ChatGPT Image Jul 9, 2026, 09_59_59 PM.png" "$ICON_FILE"
fi

printf '%s\n' '#!/bin/sh' 'exec python /opt/command-centre/command_centre.py "$@"' > "$LAUNCHER"
chmod 755 "$LAUNCHER"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f /usr/share/icons/hicolor >/dev/null 2>&1 || true

echo "Installed Command Centre from GitHub main."
