# CommandOS Applications 1.1.0

Released together:

- Command Centre 1.1.0
- Command Widget 1.1.0
- Command PDF 1.1.0

## Command Centre

- Redesigned sidebar, Software Centre, Tool Library, and Offline Intelligence workspace.
- Automatic live tool inventory synchronization.
- SourceForge-backed installation and updates for all three applications.
- Improved Command PDF launch diagnostics.

## Command Widget

- Current Plasma 6 widget, telemetry collectors, HTTP service, device discovery,
  and configuration interface packaged for SourceForge installation.

## Command PDF

- PDF reading, editing, visible signatures, merge and conversion workflows.
- Dependency-light DOCX export.
- Correct launching through the installed symlink.

## Installation

```bash
curl -fLO https://linux-commandos.sourceforge.io/releases/1.1.0/install-command-centre-1.1.0.sh
chmod +x install-command-centre-1.1.0.sh
./install-command-centre-1.1.0.sh
```

The installer uses the HTTPS SourceForge package repository. No CommandOS
signing key is used. Verify downloaded release files against `SHA256SUMS` when
installing them manually.
