#!/usr/bin/env bash
set -euo pipefail

version=0.154.5
repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
install_dir="$repository_root/.tools/hugo-$version"
binary="$install_dir/hugo"

if [[ -x "$binary" ]] && "$binary" version | grep -q "v$version"; then
  printf '%s\n' "$binary"
  exit 0
fi

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64|Darwin-x86_64)
    asset="hugo_extended_${version}_darwin-universal.pkg"
    checksum=ca2130b3f601c0f74f48ef144b3864fe14e9432243c252b5ea32f83e7a00bd49
    ;;
  Linux-x86_64)
    asset="hugo_extended_${version}_linux-amd64.tar.gz"
    checksum=372d2f0538b24d2bb9285f0583c1e3b02d023ec2c2b8eb90e5c3bbfb3139fb13
    ;;
  Linux-aarch64|Linux-arm64)
    asset="hugo_extended_${version}_linux-arm64.tar.gz"
    checksum=fb7c2275cd29ff6bfea2be09b134a0d3c9faf8f981e81e043a8f560d70f63cd3
    ;;
  *)
    echo "Unsupported Hugo platform: $(uname -s)-$(uname -m)" >&2
    exit 1
    ;;
esac

temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT
archive="$temporary/$asset"
curl --fail --location --silent --show-error \
  "https://github.com/gohugoio/hugo/releases/download/v${version}/${asset}" \
  --output "$archive"

if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$archive" | cut -d' ' -f1)
else
  actual=$(shasum -a 256 "$archive" | cut -d' ' -f1)
fi
[[ "$actual" == "$checksum" ]] || {
  echo "Hugo archive checksum mismatch" >&2
  exit 1
}

mkdir -p "$install_dir"
if [[ "$asset" == *.pkg ]]; then
  pkgutil --expand-full "$archive" "$temporary/expanded"
  install -m 0755 "$temporary/expanded/Payload/hugo" "$binary"
else
  tar -xzf "$archive" -C "$temporary"
  install -m 0755 "$temporary/hugo" "$binary"
fi
"$binary" version | grep -q "v$version"
printf '%s\n' "$binary"
