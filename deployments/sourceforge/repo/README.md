# CommandOS SourceForge Package Repository

Public URL:

```text
https://linux-commandos.sourceforge.io/repo/x86_64
```

The repository publishes Command Centre, Command Widget, and Command PDF 1.1.0.
Configure pacman with:

```ini
[commandos]
SigLevel = Never
Server = https://linux-commandos.sourceforge.io/repo/x86_64
```

No CommandOS signing key is used. `SHA256SUMS` accompanies the release artifacts.
Build the complete upload tree with `scripts/build-sourceforge-release.sh`.
