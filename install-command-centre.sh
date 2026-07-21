#!/usr/bin/env bash
set -euo pipefail

version=1.1.0
repository_url=https://linux-commandos.sourceforge.io/repo/x86_64

if ! command -v pacman >/dev/null 2>&1; then
  echo "Command Centre $version requires an Arch Linux compatible system with pacman." >&2
  exit 1
fi
command -v curl >/dev/null || { echo "curl is required." >&2; exit 1; }

echo "Command Centre $version installer"
echo "Source: $repository_url"
curl --fail --silent --show-error --location "$repository_url/commandos.db" --output /dev/null

temporary_conf=$(mktemp)
trap 'rm -f -- "$temporary_conf"' EXIT
awk -v server="$repository_url" '
  BEGIN { in_commandos=0; found=0 }
  /^\[commandos\][[:space:]]*$/ {
    found=1; in_commandos=1
    print "[commandos]"
    print "SigLevel = Never"
    print "Server = " server
    next
  }
  in_commandos && /^\[/ { in_commandos=0 }
  in_commandos && /^(SigLevel|Server)[[:space:]]*=/ { next }
  { print }
  END {
    if (!found) {
      print ""
      print "[commandos]"
      print "SigLevel = Never"
      print "Server = " server
    }
  }
' /etc/pacman.conf > "$temporary_conf"

echo "Configuring the SourceForge CommandOS repository..."
sudo cp --preserve=mode,ownership,timestamps /etc/pacman.conf "/etc/pacman.conf.commandos-backup"
sudo install -m 0644 "$temporary_conf" /etc/pacman.conf
sudo pacman -Syyu --needed command-centre

echo
echo "Command Centre $version is installed. Launch it from the application menu or run: command-centre"
