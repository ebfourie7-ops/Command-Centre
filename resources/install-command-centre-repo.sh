#!/usr/bin/env bash
set -euo pipefail

fingerprint=D6D28256B728685F4D4426A2A8214620EA123648
key_url=https://linux-commandos.sourceforge.io/repo/x86_64/commandos-repo-key.asc
repository_url=https://linux-commandos.sourceforge.io/repo/x86_64
temporary_key=$(mktemp)
trap 'rm -f -- "$temporary_key"' EXIT

command -v curl >/dev/null || { echo "curl is required to configure the Command Centre repository." >&2; exit 1; }
command -v gpg >/dev/null || { echo "gpg is required to verify the Command Centre repository key." >&2; exit 1; }

echo "Downloading the Command Centre public repository key..."
curl --fail --silent --show-error --location "$key_url" --output "$temporary_key"
downloaded_fingerprint=$(gpg --batch --show-keys --with-colons "$temporary_key" | awk -F: '$1 == "fpr" {print $10; exit}')
if [[ "$downloaded_fingerprint" != "$fingerprint" ]]; then
  echo "Repository key verification failed." >&2
  echo "Expected: $fingerprint" >&2
  echo "Received: ${downloaded_fingerprint:-none}" >&2
  exit 1
fi

echo "Verified repository key: $fingerprint"
sudo pacman-key --add "$temporary_key"
sudo pacman-key --lsign-key "$fingerprint"

if ! grep -Eq '^\[commandos\][[:space:]]*$' /etc/pacman.conf; then
  echo "Adding the signed CommandOS repository to /etc/pacman.conf..."
  sudo cp --preserve=mode,ownership,timestamps /etc/pacman.conf "/etc/pacman.conf.commandos-backup"
  printf '\n[commandos]\nSigLevel = Required DatabaseOptional\nServer = %s\n' "$repository_url" \
    | sudo tee -a /etc/pacman.conf >/dev/null
else
  echo "CommandOS repository is already configured."
fi

echo "Synchronizing repositories and updating Command Centre..."
sudo pacman -Syu --needed command-centre

echo
echo "Command Centre update complete. Restart the application to load the new version."
read -n 1 -s -r -p "Press any key to close this terminal..."
