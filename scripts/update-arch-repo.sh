#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
package_root="$project_root/packaging/arch"
repository_root="$project_root/arch-repo/x86_64"
repository_name=command-centre

mkdir -p -- "$repository_root"

(
  cd -- "$package_root"
  makepkg --cleanbuild --force --noconfirm
)

package=$(find "$package_root" -maxdepth 1 -type f -name 'command-centre-*.pkg.tar.zst' -printf '%T@ %p\n' \
  | sort -nr | awk 'NR == 1 {sub(/^[^ ]+ /, ""); print; exit}')
if [[ -z "$package" ]]; then
  echo "No Command Centre package was produced." >&2
  exit 1
fi

install -m 0644 -- "$package" "$repository_root/"

if [[ -n "${REPO_SIGN_KEY:-}" ]]; then
  rm -f -- "$repository_root/$(basename -- "$package").sig"
  gpg --batch --yes --local-user "$REPO_SIGN_KEY" --detach-sign -- "$repository_root/$(basename -- "$package")"
  repo-add --sign --key "$REPO_SIGN_KEY" --remove \
    "$repository_root/$repository_name.db.tar.gz" "$repository_root/$(basename -- "$package")"
  gpg --armor --export "$REPO_SIGN_KEY" > "$project_root/arch-repo/command-centre-repo-key.asc"
else
  repo-add --remove "$repository_root/$repository_name.db.tar.gz" "$repository_root/$(basename -- "$package")"
  echo "Repository generated without signatures. Set REPO_SIGN_KEY to a GPG key fingerprint to sign future updates." >&2
fi

# GitHub Pages and basic static servers do not reliably dereference repository
# symlinks, so publish concrete copies at the names pacman requests.
rm -f -- "$repository_root/$repository_name.db" "$repository_root/$repository_name.files" \
  "$repository_root/$repository_name.db.sig" "$repository_root/$repository_name.files.sig"
cp -- "$repository_root/$repository_name.db.tar.gz" "$repository_root/$repository_name.db"
cp -- "$repository_root/$repository_name.files.tar.gz" "$repository_root/$repository_name.files"
if [[ -f "$repository_root/$repository_name.db.tar.gz.sig" ]]; then
  cp -- "$repository_root/$repository_name.db.tar.gz.sig" "$repository_root/$repository_name.db.sig"
fi
if [[ -f "$repository_root/$repository_name.files.tar.gz.sig" ]]; then
  cp -- "$repository_root/$repository_name.files.tar.gz.sig" "$repository_root/$repository_name.files.sig"
fi
rm -f -- "$repository_root/$repository_name.db.tar.gz.old" "$repository_root/$repository_name.files.tar.gz.old" \
  "$repository_root/$repository_name.db.tar.gz.old.sig" "$repository_root/$repository_name.files.tar.gz.old.sig"

printf 'Repository updated: %s\nPackage: %s\n' "$repository_root" "$(basename -- "$package")"
