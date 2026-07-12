# Contributing to Command Centre

Use an Arch/CachyOS workstation with Python, PySide6, Qt WebEngine, and
`python-cryptography`. Do not test privileged actions on a production system.

## Before changing code

1. Read `ARCHITECTURE.md` and identify the owning module.
2. Keep process execution in `core/shell_actions.py`.
3. Pass user-controlled values as arguments, never interpolated shell text.
4. Add validation and a hostile-input regression test for every new command or
   user-editable configuration field.
5. Require confirmation for package, kernel, service, boot, snapshot, network,
   power, and destructive file actions.

## Validation

Run:

```bash
python -m py_compile command_centre.py command_intel.py core/*.py
python -m unittest discover -s tests -v
shellcheck resources/update-command-centre.sh resources/command-widget/daemon/telemetry-daemon.sh start.sh
desktop-file-validate "Command Centre.desktop" packaging/arch/command-centre.desktop
git diff --check
```

For UI changes, instantiate `MainWindow` with the offscreen Qt platform and open
all seven modules. Package changes must also pass `makepkg --printsrcinfo`.

## Review expectations

Keep commits focused. Describe security boundaries and failure behavior in the
review. Never commit case data, credentials, local chat logs, generated packages,
ISO build trees, or other user state.
