#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "📦 Starting WhisperServe development environment..."

# Check if dotenvx is installed
if ! command -v dotenvx &> /dev/null; then
    echo "❌ dotenvx is not installed. Please run setup-dev.bash first."
    exit 1
fi

# Check if tilt is installed
if ! command -v tilt &> /dev/null; then
    echo "❌ tilt is not installed. Please install tilt: https://docs.tilt.dev/install.html"
    exit 1
fi

# Load environment variables and start tilt
echo "🚀 Loading environment variables and starting Tilt..."
dotenvx run -- tilt up

echo "✨ Tilt started successfully!"
