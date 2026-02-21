#!/usr/bin/env bash
set -euo pipefail

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/taskx-determinism.XXXXXX")"
cleanup() {
  rm -rf "$tmpdir"
}
trap cleanup EXIT

hashes1="$tmpdir/hashes1.txt"
hashes2="$tmpdir/hashes2.txt"

uv build
sha256sum dist/*.whl > "$hashes1"

rm -rf dist
uv build
sha256sum dist/*.whl > "$hashes2"

diff -u "$hashes1" "$hashes2"

echo "Deterministic wheel build verified."
