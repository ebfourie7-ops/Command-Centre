#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(cat "$ROOT_DIR/VERSION")"
BIN_DIR="$HOME/.local/bin"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/telemetry"
SYSTEMD_DIR="$HOME/.config/systemd/user"
WIDGET_DIR="$HOME/.local/share/plasma/plasmoids/telemetrywidget"

mkdir -p "$BIN_DIR" "$STATE_DIR" "$SYSTEMD_DIR" "$WIDGET_DIR"

install -m 755 "$ROOT_DIR/daemon/telemetry-daemon.sh" "$BIN_DIR/telemetry-daemon"
install -m 755 "$ROOT_DIR/daemon/telemetry-http-daemon.py" "$BIN_DIR/telemetry-http-daemon"
install -m 755 "$ROOT_DIR/daemon/telemetry-devices.py" "$BIN_DIR/telemetry-devices"
install -m 755 "$ROOT_DIR/widget/telemetry-widget.sh" "$BIN_DIR/telemetry-widget"
install -m 644 "$ROOT_DIR/systemd/telemetry-daemon.service" "$SYSTEMD_DIR/telemetry-daemon.service"
install -m 644 "$ROOT_DIR/systemd/telemetry-http-daemon.service" "$SYSTEMD_DIR/telemetry-http-daemon.service"
cp -R "$ROOT_DIR/widget/." "$WIDGET_DIR/"

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload >/dev/null 2>&1 || true
  systemctl --user enable --now telemetry-daemon.service >/dev/null 2>&1 || true
  systemctl --user enable --now telemetry-http-daemon.service >/dev/null 2>&1 || true
fi

echo "Installed Command Widget v$VERSION."
echo "Daemon binary: $BIN_DIR/telemetry-daemon"
echo "HTTP daemon binary: $BIN_DIR/telemetry-http-daemon"
echo "Widget script: $BIN_DIR/telemetry-widget"
echo "State directory: $STATE_DIR"
echo "HTTP endpoint: http://127.0.0.1:9090/telemetry"
