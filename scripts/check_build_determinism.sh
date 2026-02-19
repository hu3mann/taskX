#!/usr/bin/env bash
set -euo pipefail

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

rm -rf dist
uv build
sha256sum dist/*.whl > "${TMPDIR}/hashes1.txt"

rm -rf dist
uv build
sha256sum dist/*.whl > "${TMPDIR}/hashes2.txt"

diff -u "${TMPDIR}/hashes1.txt" "${TMPDIR}/hashes2.txt"

echo "Deterministic wheel build verified."
