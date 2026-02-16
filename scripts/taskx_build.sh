#!/usr/bin/env bash
# TaskX build script - Builds sdist + wheel and validates with twine

set -euo pipefail

echo "=== TaskX Build Script ==="
echo "Building distribution packages..."

# Ensure clean dist directory
if [ -d "dist" ]; then
    echo "Cleaning existing dist/ directory..."
    rm -rf dist/
fi

# Build sdist and wheel using uv
echo "Building sdist and wheel..."
uv build

# Check that artifacts were created
if [ ! -d "dist" ] || [ -z "$(ls -A dist/)" ]; then
    echo "❌ Error: dist/ directory is empty after build"
    exit 1
fi

echo "Built packages:"
ls -lh dist/

# Validate with twine via uvx
echo "Validating packages with twine..."
uvx twine check dist/*

echo "✅ Build complete and validated"
