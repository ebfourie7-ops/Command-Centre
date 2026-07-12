# Command Centre Arch Repository

The pacman repository database and packages are under `x86_64/`. Despite that
directory name, Command Centre is currently an architecture-independent `any`
package and can be served from this standard repository path.

## Update the repository

```bash
./scripts/update-arch-repo.sh
```

To sign the package and database after configuring a GPG secret key:

```bash
REPO_SIGN_KEY=FULL_KEY_FINGERPRINT ./scripts/update-arch-repo.sh
```

The script performs a clean package build, copies the newest package, removes
obsolete versions from the database, and regenerates `command-centre.db` and
`command-centre.files`.

## Use the public repository

Import and locally trust the dedicated repository key:

```bash
curl -fsSLO https://ebfourie7-ops.github.io/Command-Centre/arch-repo/command-centre-repo-key.asc
sudo pacman-key --add command-centre-repo-key.asc
sudo pacman-key --lsign-key D6D28256B728685F4D4426A2A8214620EA123648
```

Repository signing-key fingerprint:

```text
D6D2 8256 B728 685F 4D44  26A2 A821 4620 EA12 3648
```

Verify it against more than one trusted project channel before locally signing
it.

Add this block to `/etc/pacman.conf`, above the standard repositories:

```ini
[command-centre]
SigLevel = Required DatabaseOptional
Server = https://ebfourie7-ops.github.io/Command-Centre/arch-repo/x86_64
```

Then install normally:

```bash
sudo pacman -Syy
sudo pacman -S command-centre
```

## Use the local repository

Add this block to `/etc/pacman.conf`, above the standard repositories:

```ini
[command-centre]
SigLevel = Optional TrustAll
Server = file:///home/eugene/Desktop/Code/Command%20Centre/arch-repo/x86_64
```

Then synchronize and install:

```bash
sudo pacman -Syy
sudo pacman -S command-centre
```

`Optional TrustAll` is suitable only for local development. Public clients must
use the signed configuration above.

## Hosting

Serve the contents of `arch-repo/x86_64` through any static HTTPS host. Replace
the local `Server` value with the public directory URL. Keep the repository URL
stable across application releases; package versions belong in the database,
not in the server path.
