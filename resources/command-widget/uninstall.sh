#!/usr/bin/env bash
set -euo pipefail

BIN_DIR="$HOME/.local/bin"
SYSTEMD_DIR="$HOME/.config/systemd/user"
WIDGET_DIR="$HOME/.local/share/plasma/plasmoids/telemetrywidget"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/telemetry"

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user disable telemetry-http-daemon.service >/dev/null 2>&1 || true
  systemctl --user stop telemetry-http-daemon.service >/dev/null 2>&1 || true
  systemctl --user disable telemetry-daemon.service >/dev/null 2>&1 || true
  systemctl --user stop telemetry-daemon.service >/dev/null 2>&1 || true
  systemctl --user daemon-reload >/dev/null 2>&1 || true
fi

rm -f "$BIN_DIR/telemetry-daemon" "$BIN_DIR/telemetry-http-daemon" "$BIN_DIR/telemetry-devices" "$BIN_DIR/telemetry-widget"
rm -f "$SYSTEMD_DIR/telemetry-daemon.service" "$SYSTEMD_DIR/telemetry-http-daemon.service"
rm -rf "$WIDGET_DIR"
rm -f "$STATE_DIR/telemetry.json" "$STATE_DIR/telemetry-daemon.pid" "$STATE_DIR/telemetry-http.pid" \
  "$STATE_DIR/network.sample" "$STATE_DIR/storage.sample" "$STATE_DIR/storage-devices.sample" \
  "$STATE_DIR/storage-devices.health.json" "$STATE_DIR/storage-devices.network.json"
rmdir "$STATE_DIR" >/dev/null 2>&1 || true

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload >/dev/null 2>&1 || true
fi

echo "Removed Command Widget telemetry package."
