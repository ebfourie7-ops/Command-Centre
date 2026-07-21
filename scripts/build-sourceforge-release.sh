#!/usr/bin/env bash
set -euo pipefail

release_version=1.1.0
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
repository_root="$project_root/deployments/sourceforge/repo/x86_64"
release_root="$project_root/deployments/sourceforge/releases/$release_version"

mkdir -p -- "$repository_root" "$release_root"

if [[ -f "$repository_root/commandos.db.tar.gz" ]]; then
  repo-remove "$repository_root/commandos.db.tar.gz" commandos-keyring >/dev/null 2>&1 || true
fi
find "$repository_root" -maxdepth 1 -type f -name 'commandos-keyring-*.pkg.tar.zst*' -delete

for component in arch pdf widget; do
  (
    cd -- "$project_root/packaging/$component"
    makepkg --cleanbuild --force --noconfirm --nodeps
  )
done

for package_name in command-centre command-pdf command-widget; do
  package=$(find "$project_root/packaging" -maxdepth 2 -type f -name "$package_name-$release_version-*.pkg.tar.zst" -printf '%T@ %p\n' \
    | sort -nr | awk 'NR == 1 {sub(/^[^ ]+ /, ""); print; exit}')
  [[ -n "$package" ]] || { echo "Missing package for $package_name $release_version" >&2; exit 1; }
  find "$repository_root" -maxdepth 1 -type f -name "$package_name-*.pkg.tar.zst" -delete
  install -m 0644 "$package" "$repository_root/"
  install -m 0644 "$package" "$release_root/"
done

rm -f -- "$repository_root"/command-centre-*.sig "$repository_root"/command-pdf-*.sig \
  "$repository_root"/command-widget-*.sig "$repository_root"/commandos.db*.sig \
  "$repository_root"/commandos.files*.sig "$release_root"/*.sig
repo-add --remove "$repository_root/commandos.db.tar.gz" \
  "$repository_root"/command-centre-$release_version-*.pkg.tar.zst \
  "$repository_root"/command-pdf-$release_version-*.pkg.tar.zst \
  "$repository_root"/command-widget-$release_version-*.pkg.tar.zst

rm -f -- "$repository_root/commandos.db" "$repository_root/commandos.files"
cp -- "$repository_root/commandos.db.tar.gz" "$repository_root/commandos.db"
cp -- "$repository_root/commandos.files.tar.gz" "$repository_root/commandos.files"
rm -f -- "$repository_root"/*.old "$repository_root"/*.old.sig

install -m 0755 "$project_root/install-command-centre.sh" "$release_root/install-command-centre-$release_version.sh"
(
  cd -- "$release_root"
  sha256sum -- *.pkg.tar.zst install-command-centre-$release_version.sh > SHA256SUMS
)
install -m 0644 "$release_root/SHA256SUMS" "$repository_root/SHA256SUMS"

printf 'SourceForge release prepared:\n  Repository: %s\n  Release: %s\n' "$repository_root" "$release_root"
