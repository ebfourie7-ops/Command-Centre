# Command Centre

Command Centre is a native Python/PySide6 desktop application for the CommandOS operations dashboard and control layer.

## Current Features

- Native desktop GUI, not browser based
- Persistent SQLite-backed System Timeline with structured, deduplicated system and Command Centre events
- Transparent weighted Command OS Readiness Score with a visible progress bar and deduction breakdown
- Live dashboard using the Command Widget telemetry service
- Confirm-first controls for changing actions
- Command palette with `Ctrl+K`
- Main tabs for System Dashboard, Tool Library, Command Apps, Command Terminal, Command Intel, Offline Knowledge, and Software Centre
- Command Apps catalogue with descriptions, installation-state detection, confirm-first installers, a bundled offline Command Widget installer/update action, and live controls for Command Hello, Calamares, and the CommandOS CLI installer
- Command Apps includes user-local install, update, open, and uninstall controls for the bundled Command PDF reader, converter, editor, and visible-signature app
- Command Apps directs installed systems to reviewed package updates; direct branch downloads and privileged source-tree execution are disabled
- Software Centre includes update checks, package search, confirm-first install/remove actions, Flatpak updates, package list export, and maintenance command previews
- Software Centre provides selectable orphan and foreign-package management with inspect, keep, update/rebuild, and confirmed removal actions
- Software Centre includes a Kernel Manager for listing, installing, and removing kernels through `chwd-kernel`, plus initramfs and GRUB rebuild actions
- Tool Library auto-refreshes from live pacman, Flatpak, desktop launcher, and executable scans, with launch, terminal, install, and guide actions
- Command Terminal provides a VS Code-style workspace with explorer, editor tabs, save/save-all, terminal/output, and an in-app local HTML preview
- Command Terminal includes a right-side Codex chat panel with Ask, Agent, Edit, and Review modes
- Agent Hub includes persistent task records with live Plan, Changes, command status, file activity, token usage, elapsed time, pause/stop, diff review, and an auditable activity log
- Write-capable Codex tasks use a read-only planning pass, structured impact estimates, editable plans, explicit approval, and an automatic pre-execution checkpoint before workspace changes begin
- Command Terminal provides inspectable Observe, Safe, Develop, Elevated, and Autonomous permission profiles plus automatic pre-task checkpoints for write-capable agent tasks
- Agent Hub keeps local per-session JSONL chat history, supplies recent history to agents, and provides controls to view, start, delete, and open the stored logs
- Agent Hub provides provider-aware login, logout, and account-status controls for Codex, Claude, Ollama, FCC Claude, and API-key agents
- Command Terminal can start `codex login` to link your ChatGPT/OpenAI account and check login status
- Command Terminal shows Codex usage as tracked tokens used against a local limit you set
- Command Intel provides query-once OSINT launchers for usernames, email addresses, domains, IPs, phones, people, and companies, with selected-provider launching and a locally saved investigation workspace
- Command Intel now includes SQLite-backed cases, hashed evidence imports, browser screenshots, integrity verification, HTML reports, structured entities and relationships, and a visual investigation graph
- Its research browser supports multiple tabs, ad/tracker blocking, standard and JavaScript-disabled privacy modes, external-browser handoff, and direct capture into the active case
- Tool and workflow support detects common local OSINT utilities, launches authorized jobs in a terminal, and provides a repeatable domain-research workflow
- Command AI provides deterministic case summaries and evidence-grounded local analysis through Ollama when a local model is available
- The v0.2-alpha hardening layer adds automatic database migrations, database backups, case archives, authorization and scope records, exportable ZIP case bundles, case-isolated browser storage/downloads, ad-block allowlisting, rendered HTML capture, structured JSON result imports, strict URL validation, crash reports, and automated data-layer tests
- Command Intel supports password-protected cases with PBKDF2-derived AES-256-GCM encryption for sensitive database fields and copied evidence files; keys remain in memory only while a case is unlocked
- Command Intel cases can be exported as collision-safe ZIP bundles, HTML reports, printable PDFs, or sent through the system print dialog, with explicit warnings before protected data is decrypted for output
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

## Version 1.1.0

Command Centre, Command Widget, and Command PDF are released together as version
`1.1.0`. This release adds the redesigned application navigation, Software Centre,
Tool Library, Offline Intelligence workspace, SourceForge package installation,
and system-managed Command Apps updates.

Command Intel stores its case database and copied evidence under:

```text
~/.local/share/command-centre/intel/
```

Crash reports are written to `~/.local/state/command-centre/crash.log`. Arch packaging files are under `packaging/arch/`.

The project publishes the `[commandos]` pacman repository at
`https://linux-commandos.sourceforge.io/repo/x86_64`.
Build the complete SourceForge release with `./scripts/build-sourceforge-release.sh`.

## Install on Arch Linux

Download and run the installer:

```bash
curl -fLO https://linux-commandos.sourceforge.io/releases/1.1.0/install-command-centre-1.1.0.sh
chmod +x install-command-centre-1.1.0.sh
./install-command-centre-1.1.0.sh
```

Add the repository above the standard repositories in `/etc/pacman.conf`:

```ini
[commandos]
SigLevel = Never
Server = https://linux-commandos.sourceforge.io/repo/x86_64
```

Install Command Centre normally through pacman:

```bash
sudo pacman -Syy
sudo pacman -S command-centre
```

Command Apps installs and updates `command-widget` and `command-pdf` from the same
SourceForge repository. **UPDATE COMMAND CENTRE** configures the repository and
opens the normal pacman update flow.

Privileged and system command activity is recorded in a private rotating JSONL
audit log at `~/.local/state/command-centre/actions.jsonl`. Developer-facing
module boundaries and security rules are documented in `ARCHITECTURE.md` and
`CONTRIBUTING.md`.

Bundled Command Widget and Command PDF payloads remain available for development;
published installations and updates use the SourceForge packages.

Run the automated checks with:

```bash
python -m unittest discover -s tests -v
python -m py_compile command_centre.py command_intel.py core/*.py
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
