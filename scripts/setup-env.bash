#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TOOL_VERSIONS_FILE="${PROJECT_ROOT}/.tool-versions"

echo "📦 Setting up development environment..."

# Check if asdf is installed
if ! command -v asdf &> /dev/null; then
    echo "❌ asdf is not installed. Please install asdf first: https://asdf-vm.com/guide/getting-started.html"
    exit 1
fi

# Check if system dependencies are installed (for Ubuntu/Debian)
check_system_dependencies() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        if [[ "$ID" == "ubuntu" || "$ID" == "debian" || "$ID_LIKE" == *"ubuntu"* || "$ID_LIKE" == *"debian"* ]]; then
            echo "🔍 Checking for required system dependencies on $NAME..."
            
            MISSING_DEPS=()
            
            # Check for libsqlite3-dev
            if ! dpkg -s libsqlite3-dev >/dev/null 2>&1; then
                MISSING_DEPS+=("libsqlite3-dev")
            fi
            
            # Check for libbz2-dev (for bz2 support)
            if ! dpkg -s libbz2-dev >/dev/null 2>&1; then
                MISSING_DEPS+=("libbz2-dev")
            fi
            
            # Check for liblzma-dev (for lzma support)
            if ! dpkg -s liblzma-dev >/dev/null 2>&1; then
                MISSING_DEPS+=("liblzma-dev")
            fi
            
            # Add more dependency checks here as needed
            
            if [[ ${#MISSING_DEPS[@]} -gt 0 ]]; then
                echo "⚠️ Missing required system dependencies: ${MISSING_DEPS[*]}"
                echo "💻 Please install them with:"
                echo "sudo apt-get update && sudo apt-get install -y ${MISSING_DEPS[*]}"
                
                read -p "Would you like to install these dependencies now? (y/n) " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    sudo apt-get update && sudo apt-get install -y "${MISSING_DEPS[@]}"
                    echo "✅ Dependencies installed. Python will need to be reinstalled."
                    return 1  # Signal that we need to reinstall Python
                else
                    echo "⚠️ Dependencies not installed. Setup may fail."
                    return 1  # Signal that we need to reinstall Python
                fi
            else
                echo "✅ All system dependencies are installed."
                return 0
            fi
        fi
    fi
    
    # For non-Ubuntu/Debian systems, just continue
    return 0
}


# Check if Python has SQLite3, bz2, and lzma support
check_python_modules_support() {
    echo "🔍 Checking for required Python modules..."
    
    local missing_modules=0
    
    # Check for SQLite3
    if ! python -c "import sqlite3" 2>/dev/null; then
        echo "❌ SQLite3 support is missing in Python."
        missing_modules=1
    else
        echo "✅ SQLite3 support is available in Python."
    fi
    
    # Check for bz2
    if ! python -c "import bz2" 2>/dev/null; then
        echo "❌ bz2 support is missing in Python."
        missing_modules=1
    else
        echo "✅ bz2 support is available in Python."
    fi
    
    # Check for lzma
    if ! python -c "import lzma" 2>/dev/null; then
        echo "❌ lzma support is missing in Python."
        missing_modules=1
    else
        echo "✅ lzma support is available in Python."
    fi
    
    return $missing_modules
}


# Reinstall Python if needed
reinstall_python_if_needed() {
    local need_reinstall=0
    
    # Check system dependencies first
    check_system_dependencies
    need_reinstall=$?
    
    # Check SQLite3 support
    if [[ $need_reinstall -eq 0 ]]; then
        check_python_modules_support
        need_reinstall=$?
    fi
    
    if [[ $need_reinstall -eq 1 ]]; then
        echo "🔄 Python needs to be reinstalled to include SQLite3 support."
        
        # Get current Python version from asdf
        local python_version=$(asdf current python | awk '{print $2}')
        if [[ -z "$python_version" ]]; then
            # Try to get from .tool-versions
            python_version=$(grep "^python " "${TOOL_VERSIONS_FILE}" 2>/dev/null | awk '{print $2}' || echo "")
        fi
        
        if [[ -z "$python_version" ]]; then
            echo "❌ Could not determine Python version. Please reinstall Python manually with asdf."
            return 1
        fi
        
        echo "🔄 Reinstalling Python ${python_version}..."
        asdf uninstall python "${python_version}"
        asdf install python "${python_version}"
        
        # Verify SQLite3 now works
        if ! python -c "import sqlite3" 2>/dev/null; then
            echo "❌ SQLite3 support is still missing after reinstall. Please check your system configuration."
            return 1
        fi
        
        echo "✅ Python reinstalled with SQLite3 support."
    fi
    
    return 0
}

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

# Check and reinstall Python if needed
reinstall_python_if_needed

# Install dotenvx for environment management
echo "🌱 Setting up dotenvx..."
if ! command -v dotenvx &> /dev/null; then
    echo "⬇️ Installing dotenvx..."
    npm install -g @dotenvx/dotenvx
else
    echo "✅ dotenvx already installed"
fi

# Ensure Poetry is installed
echo "📝 Checking Poetry installation..."
if ! command -v poetry &> /dev/null; then
    echo "⬇️ Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    
    # Add Poetry to PATH if not already there
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
        export PATH="$HOME/.local/bin:$PATH"
    fi
else
    echo "✅ Poetry already installed"
fi

# Install poetry dependencies
echo "📚 Installing Poetry dependencies..."
cd "${PROJECT_ROOT}"
poetry install

echo "✨ Development environment setup complete!"
echo "🚀 You can now run 'poetry run whisperserve' to start the service"
