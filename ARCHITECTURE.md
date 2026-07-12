# Command Centre Architecture

Command Centre is a native PySide6 application for CommandOS/CachyOS. The main
window composes seven visible modules: Dashboard, Tool Library, Command Apps,
Command Terminal, Command Intel, Offline Knowledge, and Software Centre.

## Current boundaries

- `command_centre.py` contains the window and UI pages. Pages will be extracted
  incrementally to `ui/`; this avoids a high-risk all-at-once rewrite.
- `command_intel.py` owns cases, encrypted evidence, investigation workflows,
  exports, and print support.
- `core/events.py` owns the SQLite System Timeline and state-transition dedupe.
- `core/telemetry.py` owns the HTTP telemetry contract and local JSON fallback.
- `core/shell_actions.py` validates arguments, launches audited processes, and
  writes the private structured action log.
- `core/config_schema.py` validates user-editable agent and deployment JSON.

## Security boundaries

Argument-list execution is the default. Shell scripts are reserved for reviewed
built-in workflows that need pipelines, interactive prompts, or terminal
composition. User-editable deployment app commands must parse as a single
program plus arguments; shell operators are rejected. Custom terminal and quick
action commands follow the same rule.

Every routed command is written to
`~/.local/state/command-centre/actions.jsonl`. The log is mode `0600`, rotates at
5 MiB, and contains the action, arguments, status, exit code, and bounded error
detail. Secrets must never be included in arguments or log details.

Mutating UI actions require visible confirmation before launch. Privileged work
must run in a terminal so the operating system owns authentication.

## Telemetry contract

The primary source is `http://127.0.0.1:9090/telemetry`. When unavailable, the
client reads `~/.local/state/telemetry/telemetry.json`. Telemetry must be a JSON
object; malformed or differently shaped data becomes an empty reading.

## Private data

Configuration uses `~/.config/command-centre`; investigations use
`~/.local/share/command-centre`; logs use `~/.local/state/command-centre`.
Directories are `0700` and files are `0600`.

## Extraction plan

Future UI extraction should proceed one page per reviewed change: Dashboard,
Software Centre, Tool Library, Command Terminal, Offline Knowledge, then dormant
System Control and Deployment code. Each extraction must preserve imports,
signals, tests, and the seven-module smoke test.
