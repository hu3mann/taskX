#!/usr/bin/env bash
# TaskX install test - Creates temp venv, installs wheel, and runs doctor

set -euo pipefail

echo "=== TaskX Install Test ==="

# Find the wheel file
WHEEL_FILE=$(find dist/ -name "*.whl" | head -n 1)

if [ -z "$WHEEL_FILE" ]; then
    echo "❌ Error: No wheel file found in dist/"
    exit 1
fi

echo "Testing wheel: $WHEEL_FILE"

# Create temporary venv
TEMP_VENV=$(mktemp -d -t taskx-test-venv.XXXXXX)
echo "Creating temporary venv: $TEMP_VENV"

uv venv "$TEMP_VENV"

# Activate venv
if [ -f "$TEMP_VENV/bin/activate" ]; then
    # Unix-like
    source "$TEMP_VENV/bin/activate"
elif [ -f "$TEMP_VENV/Scripts/activate" ]; then
    # Windows
    source "$TEMP_VENV/Scripts/activate"
else
    echo "❌ Error: Cannot find venv activation script"
    rm -rf "$TEMP_VENV"
    exit 1
fi

# Install wheel
echo "Installing wheel..."
uv pip install "$WHEEL_FILE" --quiet

# Test 1: taskx --help
echo "Test 1: taskx --help"
if ! taskx --help > /dev/null 2>&1; then
    echo "❌ Error: taskx --help failed"
    deactivate
    rm -rf "$TEMP_VENV"
    exit 1
fi
echo "✅ taskx --help works"

# Test 2: taskx doctor
echo "Test 2: taskx doctor"
DOCTOR_OUT=$(mktemp -d -t taskx-doctor-test.XXXXXX)

if ! taskx doctor --timestamp-mode deterministic --out "$DOCTOR_OUT"; then
    echo "❌ Error: taskx doctor failed"
    cat "$DOCTOR_OUT/DOCTOR_REPORT.md" || true
    deactivate
    rm -rf "$TEMP_VENV"
    rm -rf "$DOCTOR_OUT"
    exit 1
fi
echo "✅ taskx doctor passed"

# Cleanup
deactivate
rm -rf "$TEMP_VENV"
rm -rf "$DOCTOR_OUT"

echo "✅ All install tests passed"
