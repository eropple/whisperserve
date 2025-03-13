#!/usr/bin/env python3
"""
JWT token generator for testing - generates a valid JWT token for the WhisperServe API
using the configured JWT settings and a specified tenant ID.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add project root to path
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))

# Import required modules
from jose import jwt
from app.utils.config import load_config
from app.utils.config_utils import get_env_str

def generate_jwt(tenant_id: str, expiration_hours: int = 24) -> str:
    """
    Generate a JWT token for the given tenant ID that will work with the middleware.
    
    Args:
        tenant_id: The tenant ID to include in the token
        expiration_hours: Token validity in hours
        
    Returns:
        Generated JWT token string
    """
    # Load app config to get JWT settings
    config = load_config()
    
    # Get the signing key from environment variables
    signing_jwk_str = get_env_str("TEST__SIGNING_JWK")
    signing_jwk = json.loads(signing_jwk_str)
    
    # Prepare token claims
    now = datetime.now(timezone.utc)
    expiration = now + timedelta(hours=expiration_hours)
    
    # Create the payload
    payload = {
        "iat": int(now.timestamp()),           # Issued at
        "exp": int(expiration.timestamp()),    # Expiration
        config.jwt.tenant_claim: tenant_id,    # Tenant ID claim (configurable)
        "sub": f"test-user-{tenant_id}",       # Subject (user ID)
        "iss": "whisperserve-token-generator", # Issuer
        "aud": "whisperserve"                  # Audience - must match JWT__AUDIENCE_REGEX
    }
    
    # Create headers with key ID
    headers = {"kid": signing_jwk["kid"]}
    
    # Generate token using the signing key
    token = jwt.encode(
        payload, 
        signing_jwk,  # Pass the entire JWK
        algorithm=config.jwt.algorithm,
        headers=headers
    )
    
    return token

def main():
    """Parse command line args and generate JWT token."""
    parser = argparse.ArgumentParser(description="Generate JWT token for testing")
    parser.add_argument("tenant_id", help="Tenant ID to include in the token")
    parser.add_argument("--hours", type=int, default=24, help="Token validity in hours (default: 24)")
    parser.add_argument("--json", action="store_true", help="Output as JSON with additional info")
    
    args = parser.parse_args()
    
    try:
        token = generate_jwt(args.tenant_id, args.hours)
        
        if args.json:
            output = {
                "token": token,
                "tenant_id": args.tenant_id,
                "expires_in_hours": args.hours,
                "curl_example": f'curl -H "Authorization: Bearer {token}" http://localhost:8000/jobs'
            }
            print(json.dumps(output, indent=2))
        else:
            print(token)
            
        return 0
    except Exception as e:
        print(f"Error generating JWT: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
