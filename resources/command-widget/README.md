# Command Widget (Bundled Installer)

This KDE Plasma 6 telemetry widget installer is included with Command Centre so it can be installed on a new machine without a separate project checkout or network download.

## What It Shows

- Power mode
- CPU usage, frequency, and temperature
- RAM and GPU usage
- Storage usage and read/write speeds
- Fan, network, VPN, and battery status

## Install

Use **Command Apps → Command Widget → Install** inside Command Centre. The installer copies the widget and telemetry programs into the current user's profile and enables:

- `telemetry-daemon.service`
- `telemetry-http-daemon.service`

The local telemetry endpoint is `http://127.0.0.1:9090/telemetry`.

The installer can also be run directly from this directory with `bash install.sh`. Remove the widget with `bash uninstall.sh`.
