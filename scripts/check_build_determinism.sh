#!/usr/bin/env bash
set -euo pipefail

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

# Reuse existing build artifacts as the first build output if available,
# so CI can call this right after uv build without tripling build time.
if ! ls dist/*.whl 1>/dev/null 2>&1; then
  uv build
fi
sha256sum dist/*.whl > "${TMPDIR}/hashes1.txt"

rm -rf dist
uv build
sha256sum dist/*.whl > "${TMPDIR}/hashes2.txt"

diff -u "${TMPDIR}/hashes1.txt" "${TMPDIR}/hashes2.txt"

echo "Deterministic wheel build verified."
