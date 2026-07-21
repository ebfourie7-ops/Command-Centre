# Command Centre Development Repository

This directory contains the local Arch repository generated during Command Centre
development. Production packages for Command Centre, Command Widget, and Command
PDF are assembled under `deployments/sourceforge/repo/x86_64` with:

```bash
./scripts/build-sourceforge-release.sh
```

The public repository is hosted at:

```text
https://linux-commandos.sourceforge.io/repo/x86_64
```

Configuration:

```ini
[commandos]
SigLevel = Never
Server = https://linux-commandos.sourceforge.io/repo/x86_64
```

No CommandOS signing key is used. Release checksums are published in
`SHA256SUMS`, and packages are transported over HTTPS.
