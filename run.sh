#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Build Cython extensions (skip if already up-to-date)
echo "Building Cython extensions..."
pipenv run python "$SCRIPT_DIR/setup.py" build_ext --inplace 2>&1 | tail -1

# Run the emulator, forwarding all arguments
exec pipenv run python "$SCRIPT_DIR/main.py" "$@"
