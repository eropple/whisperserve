#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TOOL_VERSIONS_FILE="${PROJECT_ROOT}/../.tool-versions"

echo "📦 Setting up development environment..."

# Check if asdf is installed
if ! command -v asdf &> /dev/null; then
    echo "❌ asdf is not installed. Please install asdf first: https://asdf-vm.com/guide/getting-started.html"
    exit 1
fi

# Dynamically add and install plugins from .tool-versions
if [ -f "${TOOL_VERSIONS_FILE}" ]; then
    echo "🔍 Found .tool-versions file, processing..."
    
    while read -r line; do
        if [[ -z "$line" || "$line" =~ ^# ]]; then
            continue
        fi
        
        plugin=$(echo "$line" | awk '{print $1}')
        version=$(echo "$line" | awk '{print $2}')
        
        echo "🔧 Processing plugin: $plugin ($version)"
        
        # Check if plugin is already added
        if ! asdf plugin list | grep -q "^$plugin$"; then
            echo "➕ Adding asdf plugin: $plugin"
            asdf plugin add "$plugin" || echo "⚠️ Warning: couldn't add plugin $plugin, it may already exist or be unavailable"
        else
            echo "✅ Plugin $plugin already added"
        fi
    done < "${TOOL_VERSIONS_FILE}"
    
    # Install all tools specified in .tool-versions
    echo "⬇️ Installing all specified versions with asdf..."
    asdf install
else
    echo "⚠️ No .tool-versions file found at ${TOOL_VERSIONS_FILE}"
fi

# Install dotenvx for environment management
echo "🌱 Setting up dotenvx..."
if ! command -v dotenvx &> /dev/null; then
    echo "⬇️ Installing dotenvx..."
    npm install -g @dotenvx/dotenvx
else
    echo "✅ dotenvx already installed"
fi

# Install poetry dependencies
echo "📚 Installing Poetry dependencies..."
cd "${PROJECT_ROOT}"
poetry install

echo "✨ Development environment setup complete!"
echo "🚀 You can now run 'poetry run svc-up' to start the development environment"
