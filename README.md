# Command Centre

Command Centre is a native Python/PySide6 desktop application for the CommandOS operations dashboard and control layer.

## Current Features

- Native desktop GUI, not browser based
- Live dashboard using the Command Widget telemetry service
- System Control for:
  - Quick Controls with active profiles and power modes
  - Power profiles through `powerprofilesctl`
  - Wi-Fi radio through `nmcli`
  - Bluetooth power through `bluetoothctl`
  - Default audio output through `pactl`
  - System service search and terminal-confirmed service actions
  - System services search, logs, start/stop/restart, enable/disable through terminal-confirmed `systemctl`
  - Working System tool buttons that open KDE settings modules and system diagnostics
  - CommandOS profile buttons, security tools, snapshot/recovery commands, Apply Queue, and Change History
- Confirm-first controls for changing actions
- Command palette with `Ctrl+K`
- Main tabs for System Dashboard, System Control, Tool Library, Command Terminal, Offline Knowledge, Deployment Centre, and Software Centre
- Software Centre includes update checks, package search, confirm-first install/remove actions, Flatpak updates, package list export, and maintenance command previews
- Software Centre includes a Kernel Manager for listing, installing, and removing kernels through `chwd-kernel`, plus initramfs and GRUB rebuild actions
- Tool Library auto-refreshes from live pacman, Flatpak, desktop launcher, and executable scans, with launch, terminal, install, and guide actions
- Command Terminal provides a VS Code-style workspace with explorer, editor tabs, save/save-all, and terminal/output
- Command Terminal includes a right-side Codex chat panel with Ask, Agent, Edit, and Review modes
- Command Terminal can start `codex login` to link your ChatGPT/OpenAI account and check login status
- Command Terminal shows Codex usage as tracked tokens used against a local limit you set
- Command Intel provides query-once OSINT launchers for usernames, email addresses, domains, IPs, phones, people, and companies, with selected-provider launching and a locally saved investigation workspace
- Command Intel now includes SQLite-backed cases, hashed evidence imports, browser screenshots, integrity verification, HTML reports, structured entities and relationships, and a visual investigation graph
- Its research browser supports multiple tabs, ad/tracker blocking, standard and JavaScript-disabled privacy modes, external-browser handoff, and direct capture into the active case
- Tool and workflow support detects common local OSINT utilities, launches authorized jobs in a terminal, and provides a repeatable domain-research workflow
- Command AI provides deterministic case summaries and evidence-grounded local analysis through Ollama when a local model is available
- The v0.2-alpha hardening layer adds automatic database migrations, database backups, case archives, authorization and scope records, exportable ZIP case bundles, case-isolated browser storage/downloads, ad-block allowlisting, rendered HTML capture, structured JSON result imports, strict URL validation, crash reports, and automated data-layer tests
- Deployment Centre is a profile-driven mission launcher with GUI add/edit/duplicate/remove controls, using JSON templates from `deployments/default_deployments.json` and custom profiles from `~/.config/command-centre/deployment_profiles.json`
- Offline Knowledge has a single ZIM library location button, a ZIM file list, and an in-app reader

## Run

```bash
cd ~/Desktop/Code/Command\ Centre
./start.sh
```

The desktop launcher is:

```text
Command Centre.desktop
```

## Versions

- `v0.1` is the preserved baseline before the integrated Command Intel case platform.
- Current development is on the `main` branch.

Command Intel stores its case database and copied evidence under:

```text
~/.local/share/command-centre/intel/
```

Crash reports are written to `~/.local/state/command-centre/crash.log`. Arch packaging files are under `packaging/arch/`.

Run the automated checks with:

```bash
python -m unittest discover -s tests -v
python -m py_compile command_centre.py command_intel.py
```

## Notes

The app reads telemetry from:

```text
http://127.0.0.1:9090/telemetry
```

If that service is not running, it falls back to:

```text
~/.local/state/telemetry/telemetry.json
```

The old web prototype files are still present as reference, but `start.sh` now launches the native Python app.

ZIM files open inside Command Centre. The in-app reader uses `kiwix-serve` from `kiwix-tools`; Offline Knowledge includes an install button for `kiwix-tools` and `zim-tools` when the backend is missing.
