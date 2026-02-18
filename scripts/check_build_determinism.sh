#!/usr/bin/env bash
set -euo pipefail

rm -f hashes1.txt hashes2.txt

uv build
sha256sum dist/*.whl > hashes1.txt

rm -rf dist
uv build
sha256sum dist/*.whl > hashes2.txt

diff -u hashes1.txt hashes2.txt

echo "Deterministic wheel build verified."
