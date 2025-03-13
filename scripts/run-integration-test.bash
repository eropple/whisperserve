#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
INTEGRATION_DIR="${PROJECT_ROOT}/tests/integration"
SDK_DIR="${PROJECT_ROOT}/generated/sdk"

# Check if SDK exists
if [ ! -d "${SDK_DIR}" ]; then
    echo "⚠️ SDK directory not found! Run ./scripts/prepare-integration-test.bash first."
    exit 1
fi

# Make the SDK available to tests
echo "Making SDK available to tests..."
export PYTHONPATH="${SDK_DIR}:${PYTHONPATH:-}"

# Run the integration tests with Poetry
echo "Running integration tests..."
cd "${PROJECT_ROOT}" && PYTHONPATH="${SDK_DIR}:${PYTHONPATH:-}" poetry run pytest "${INTEGRATION_DIR}" -v
