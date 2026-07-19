# Command Widget

**Version 1.0.0**

Command Widget is a configurable KDE Plasma 6 system-monitoring widget. It can be installed as a standalone project or from the offline copy bundled with Command Centre.

## Features

- Power-profile status
- Total and per-core CPU usage, frequency, and temperature
- RAM usage
- Multiple dedicated and integrated GPUs with utilization, VRAM, and temperature
- Multiple storage devices with capacity, activity, temperature, and SMART health when accessible
- Fan speed and utilization
- Combined or individual Wi-Fi, Ethernet, and VPN traffic
- Battery state, charge, and power draw
- Detailed and compact layouts
- Configurable row visibility, names, order, and bar colours
- Configurable refresh interval and warning thresholds
- Automatic hiding of unavailable hardware
- Asynchronous refreshes, detailed tooltips, and stale-data warnings

## Requirements

- KDE Plasma 6
- Python 3
- Bash and standard Linux utilities including `awk`, `lsblk`, `findmnt`, and `ip`
- `nvidia-smi` for NVIDIA-specific readings
- `smartctl` for storage health details; access depends on local device permissions

Unavailable optional tools or sensors are handled gracefully.

## Install or update

Clone the standalone repository and run its installer:

```bash
git clone https://github.com/ebfourie7-ops/Command-Widget.git
cd Command-Widget
bash install.sh
```

When using Command Centre, select **Command Apps → Command Widget → Install/Update** instead; no separate clone or download is required.

The installer copies the Plasma package and collector programs into the current user profile, then enables:

- `telemetry-daemon.service`
- `telemetry-http-daemon.service`

Installed locations:

- Plasma widget: `~/.local/share/plasma/plasmoids/telemetrywidget/`
- Collector programs: `~/.local/bin/telemetry-*`
- User services: `~/.config/systemd/user/telemetry-*.service`
- Runtime state: `~/.local/state/telemetry/`

## Configure

Enter Plasma desktop Edit Mode, hover over Command Widget, and select **Configure Command Widget**. Settings include:

- visible metric rows and per-core CPU readings;
- drag-and-drop row ordering;
- custom row and device labels;
- individual GPU, storage, and network-interface selection;
- detailed or compact presentation;
- per-category bar colours;
- refresh timing and warning thresholds;
- automatic hiding of unavailable readings; and
- reset to defaults.

GPU selections use stable PCI identifiers and retain compatibility with selections saved by older builds.

## Telemetry

The HTTP service exposes the latest local snapshot at:

```text
http://127.0.0.1:9090/telemetry
```

It listens on loopback only. The same snapshot is stored at `~/.local/state/telemetry/telemetry.json` for local fallback readers.

## Uninstall

Run:

```bash
bash uninstall.sh
```

This disables the user services and removes installed Command Widget files. Runtime telemetry state is removed when possible.

## Package layout

```text
command-widget/
├── VERSION
├── daemon/       # Telemetry collectors and loopback HTTP service
├── systemd/      # User service definitions
├── widget/       # Plasma metadata, preview, settings, and UI
├── install.sh
└── uninstall.sh
```

## License

Command Widget is released under the MIT License. See `LICENSE` in the standalone repository.
