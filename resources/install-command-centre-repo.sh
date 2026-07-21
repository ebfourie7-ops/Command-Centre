#!/usr/bin/env bash
set -euo pipefail

repository_url=https://linux-commandos.sourceforge.io/repo/x86_64
packages=("${@:-command-centre}")

for package in "${packages[@]}"; do
  case "$package" in
    command-centre|command-widget|command-pdf) ;;
    *) echo "Unsupported CommandOS package: $package" >&2; exit 2 ;;
  esac
done

command -v curl >/dev/null || { echo "curl is required to configure the SourceForge repository." >&2; exit 1; }
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

sudo cp --preserve=mode,ownership,timestamps /etc/pacman.conf "/etc/pacman.conf.commandos-backup"
sudo install -m 0644 "$temporary_conf" /etc/pacman.conf

echo "Refreshing the CommandOS repository from SourceForge..."
sudo pacman -Syyu --needed "${packages[@]}"
echo "Installed or updated: ${packages[*]}"
