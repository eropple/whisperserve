#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
INTEGRATION_DIR="${PROJECT_ROOT}/tests/integration"
GENERATED_DIR="${PROJECT_ROOT}/generated"
OAS_PATH="${GENERATED_DIR}/openapi.json"
SDK_DIR="${GENERATED_DIR}/sdk"

# Clean and recreate directories
echo "Cleaning generated artifacts..."
rm -rf "${GENERATED_DIR}"
mkdir -p "${GENERATED_DIR}"
mkdir -p "${SDK_DIR}"
mkdir -p "${INTEGRATION_DIR}"

# Step 1: Generate OpenAPI spec using our CLI
echo "Generating OpenAPI specification..."
dotenvx run -- poetry run whisperserve openapi --output "${OAS_PATH}" --format json

# Step 2: Generate Python SDK from the spec with proper permissions
echo "Generating Python SDK from OpenAPI spec..."
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "${GENERATED_DIR}:/local" \
  openapitools/openapi-generator-cli generate \
  -i /local/openapi.json \
  -g python \
  -o /local/sdk \
  --additional-properties=packageName=whisperserve_client

echo "✅ Integration test SDK prepared successfully!"
