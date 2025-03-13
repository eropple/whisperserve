"""JWT utilities for token validation and information extraction."""
from typing import Optional, Any, Dict, Tuple

from jose import jwt, JWTError
from app.utils.config import AppConfig

def decode_jwt_token(
    token: str, 
    config: AppConfig, 
    raise_exceptions: bool = True
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Decode a JWT token and extract its claims.
    
    Args:
        token: The JWT token string (without 'Bearer ' prefix)
        config: Application configuration
        raise_exceptions:   If True, raises exceptions for invalid tokens
                            If False, returns None for invalid tokens

    Returns:
        Tuple of (decoded_payload, error_message)
        - If successful: (decoded_claims, None)
        - If failed with raise_exceptions=False: (None, error_message)
    
    Raises:
        ValueError: If raise_exceptions=True and token is invalid
    """
    try:
        # Get token headers without verification to extract kid
        headers = jwt.get_unverified_headers(token)
        kid = headers.get("kid")
        
        if not kid:
            if raise_exceptions:
                raise ValueError("Invalid token: missing key ID")
            return None, "Missing key ID (kid) in token"
        
        # Check if we have the key with this ID
        if kid not in config.jwt.public_keys:
            if raise_exceptions:
                raise ValueError(f"Invalid token: unknown key ID: {kid}")
            return None, f"Unknown key ID: {kid}"
        
        # Get the key and decode the token
        key = config.jwt.public_keys[kid]
        decoded = jwt.decode(
            token,
            key,
            algorithms=[config.jwt.algorithm]
        )
        
        return decoded, None
        
    except JWTError as e:
        if raise_exceptions:
            raise ValueError(f"Invalid token: {str(e)}")
        return None, f"JWT validation failed: {str(e)}"
    except Exception as e:
        if raise_exceptions:
            raise ValueError(f"Error processing token: {str(e)}")
        return None, f"Error processing token: {str(e)}"

def extract_tenant_id(
    token: str, 
    config: AppConfig, 
    raise_exceptions: bool = True
) -> Optional[str]:
    """
    Extract tenant ID from a JWT token.
    
    Args:
        token: The JWT token string (without 'Bearer ' prefix)
        config: Application configuration 
        raise_exceptions: If True, raises exceptions for invalid tokens
                         If False, returns None for invalid tokens
    
    Returns:
        Extracted tenant ID, or None if extraction failed and raise_exceptions=False
        
    Raises:
        ValueError: If raise_exceptions=True and token is invalid or missing tenant ID
    """
    decoded, error = decode_jwt_token(token, config, raise_exceptions)
    
    if decoded is None:
        return None
        
    # Extract tenant ID from the configured claim field
    tenant_id = decoded.get(config.jwt.tenant_claim)
    
    if not tenant_id and raise_exceptions:
        raise ValueError(f"Token missing required claim: {config.jwt.tenant_claim}")
        
    return str(tenant_id) if tenant_id else None
