import json
from typing import Dict, Any

from jose import jwk
from pydantic import BaseModel, Field, field_validator

from app.utils.config_utils import get_env_value, get_env_int


class JWTConfig(BaseModel):
    public_keys: Dict[str, Any] = Field(..., description="Parsed public keys from JWKS")
    algorithm: str = Field(default="ES256", description="Algorithm for JWT verification (default: ECDSA)")
    tenant_claim: str = Field(default="tenant_id", description="JWT claim field containing tenant ID")
    expiration_minutes: int = Field(default=60, description="JWT token expiration time in minutes")


def load_jwt_config() -> JWTConfig:
    """
    Load JWT configuration from environment variables.
    Parses JWKS into usable public keys.
    
    JWT__JWKS should contain a JSON Web Key Set (JWKS) string with public keys.
    """
    jwks_str = get_env_value("JWT__JWKS", required=True)
    
    # If it's a file reference, load from file
    if jwks_str.startswith("file:"):
        file_path = jwks_str[5:]
        try:
            with open(file_path, 'r') as f:
                jwks_str = f.read().strip()
        except Exception as e:
            raise ValueError(f"Failed to read JWKS from file {file_path}: {str(e)}")
    
    # Parse JWKS and extract public keys
    try:
        jwks_dict = json.loads(jwks_str)
        if not isinstance(jwks_dict.get("keys"), list):
            raise ValueError('JWKS must contain a "keys" array')
        if len(jwks_dict["keys"]) == 0:
            raise ValueError('JWKS "keys" array must not be empty')
        
        # Use jose library to parse each key in the JWKS
        public_keys = {}
        for key_dict in jwks_dict["keys"]:
            if "kid" not in key_dict:
                raise ValueError("Each key in JWKS must have a 'kid' (key ID)")
            
            try:
                key = jwk.construct(key_dict)
                # Store by key ID for easy lookup during verification
                public_keys[key_dict["kid"]] = key
            except Exception as e:
                raise ValueError(f"Failed to parse key with kid '{key_dict.get('kid')}': {str(e)}")
        
        if not public_keys:
            raise ValueError("No valid public keys found in JWKS")
            
    except json.JSONDecodeError:
        raise ValueError("JWKS must be valid JSON")
    except Exception as e:
        raise ValueError(f"Failed to parse JWKS: {str(e)}")
    
    # Default to ES256 (ECDSA with P-256 and SHA-256) 
    algorithm = get_env_value("JWT__ALGORITHM", "ES256")
    
    return JWTConfig(
        public_keys=public_keys,
        algorithm=algorithm,
        tenant_claim=get_env_value("JWT__TENANT_CLAIM", "tenant_id"),
        expiration_minutes=get_env_int("JWT__EXPIRATION_MINUTES", 60)
    )
