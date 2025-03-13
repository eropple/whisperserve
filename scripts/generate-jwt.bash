#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run the Python script using Poetry to ensure all dependencies are available
# Pass all arguments to the Python script
dotenvx run --env-file=.env.local --env-file=.env.local -- poetry run python "${SCRIPT_DIR}/generate-jwt.py" "$@"
