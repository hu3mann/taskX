#!/bin/bash
set -e

echo "Starting Google Jules, Copilot, Codex, and Claude Code Cloud setup..."

# Install TaskX
pip install -e .

# Initialize Project
echo "Initializing TaskX project..."
taskx project init --out .

# Initialize Route Availability
echo "Initializing route availability..."
taskx route init --repo-root . --force

echo "Setup complete. Verifying availability configuration..."
cat .taskx/runtime/availability.yaml

echo "Ready to serve."
