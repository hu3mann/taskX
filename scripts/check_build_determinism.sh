#!/usr/bin/env bash
set -euo pipefail

export LC_ALL=C

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

rm -rf dist
uv build
sha256sum dist/*.whl | sort > "${TMPDIR}/hashes1.txt"

rm -rf dist
uv build
sha256sum dist/*.whl | sort > "${TMPDIR}/hashes2.txt"

diff -u "${TMPDIR}/hashes1.txt" "${TMPDIR}/hashes2.txt"

echo "Deterministic wheel build verified."
