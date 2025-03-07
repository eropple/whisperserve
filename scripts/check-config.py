#!/usr/bin/env python3
"""
Configuration sanity checker - loads config from environment variables and 
prints it as formatted JSON to verify everything is loading correctly.
"""

import json
import os
import sys
from pathlib import Path

# Add debugging output to troubleshoot import issues
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent.resolve()

print(f"Script directory: {script_dir}")
print(f"Project root: {project_root}")
print(f"Contents of project root: {os.listdir(project_root)}")
print(f"Python path before: {sys.path}")

sys.path.insert(0, str(project_root))

print(f"Python path after: {sys.path}")

# Try to directly import the env module first
try:
    print("Attempting to import env module...")
    from app.utils.env import load_from_env
    print("Successfully imported env module")
except ImportError as e:
    print(f"Failed to import env module: {e}")
    
    # Check if the expected directory structure exists
    app_dir = project_root / "app"
    utils_dir = app_dir / "utils"
    env_file = utils_dir / "env.py"
    
    print(f"Checking if app directory exists: {app_dir.exists()}")
    if app_dir.exists():
        print(f"Contents of app directory: {os.listdir(app_dir)}")
        
        print(f"Checking if utils directory exists: {utils_dir.exists()}")
        if utils_dir.exists():
            print(f"Contents of utils directory: {os.listdir(utils_dir)}")
            
            print(f"Checking if env.py exists: {env_file.exists()}")

# Continue with original script...
try:
    from app.utils.config import load_config
    print("Successfully imported config module")
except ImportError as e:
    print(f"Error: Could not import config modules: {e}")
    print("Make sure the app directory structure is correct.")
    print("Are you running this script from the project root?")
    sys.exit(1)

def main():
    """Load configuration and print it as formatted JSON."""
    try:
        print("Loading configuration from environment variables...")
        config = load_config()
        
        # Convert Pydantic model to dict and then to formatted JSON
        config_json = json.dumps(
            config.model_dump(),
            indent=2,
            sort_keys=False,
            default=str  # Handle non-serializable objects
        )
        
        print("\n===== Configuration Loaded Successfully =====\n")
        print(config_json)
        print("\n============================================\n")
        
        # Check for required config sections
        required_sections = ["database", "jwt"]
        missing = [section for section in required_sections if getattr(config, section, None) is None]
        
        if missing:
            print(f"⚠️  Warning: Some required configuration sections are missing: {', '.join(missing)}")
            return 1
        
        return 0
    
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        import traceback
        print(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())