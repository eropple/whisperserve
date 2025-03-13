"""JWT utilities for token validation and information extraction."""
from typing import Optional, Any, Dict, Tuple
from fastapi import Request, HTTPException

from jose import jwt, JWTError
from app.utils.jwt_config import JWTConfig

def decode_jwt_token(
    token: str, 
    jwt_config: JWTConfig, 
    raise_exceptions: bool = True
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Decode a JWT token and extract its claims.
    
    Args:
        token: The JWT token string (without 'Bearer ' prefix)
        jwt_config: JWT configuration
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
        if kid not in jwt_config.public_keys:
            if raise_exceptions:
                raise ValueError(f"Invalid token: unknown key ID: {kid}")
            return None, f"Unknown key ID: {kid}"
        
        # Get the key and decode the token
        key = jwt_config.public_keys[kid]
        decoded = jwt.decode(
            token,
            key,
            algorithms=[jwt_config.algorithm],
            options={"verify_aud": False}
        )

        # Validate audience if regex pattern is provided
        audience = decoded['aud']
        if not audience:
            if raise_exceptions:
                raise ValueError("Invalid token: missing audience claim")
            return None, "Missing audience claim"

        # Handle both string and list audiences
        audiences = [audience] if isinstance(audience, str) else audience

        # Check if any audience matches the pattern
        if not any(jwt_config.audience_regex.match(aud) for aud in audiences):
            if raise_exceptions:
                raise ValueError(f"Invalid token audience: {audience}")
            return None, f"Invalid token audience: {audience}"
        
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
    jwt_config: JWTConfig, 
    raise_exceptions: bool = True
) -> Optional[str]:
    """
    Extract tenant ID from a JWT token.
    
    Args:
        token: The JWT token string (without 'Bearer ' prefix)
        jwt_config: JWT configuration 
        raise_exceptions: If True, raises exceptions for invalid tokens
                            If False, returns None for invalid tokens
    
    Returns:
        Extracted tenant ID, or None if extraction failed and raise_exceptions=False
        
    Raises:
        ValueError: If raise_exceptions=True and token is invalid or missing tenant ID
    """
    decoded, error = decode_jwt_token(token, jwt_config, raise_exceptions)
    
    if decoded is None:
        return None
        
    # Extract tenant ID from the configured claim field
    tenant_id = decoded.get(jwt_config.tenant_claim)
    
    if not tenant_id and raise_exceptions:
        raise ValueError(f"Token missing required claim: {jwt_config.tenant_claim}")
        
    return str(tenant_id) if tenant_id else None

def extract_tenant_id_from_request(
    request: Request,
    jwt_config: JWTConfig,
    raise_exceptions: bool = True
) -> Optional[str]:
    """
    Extract tenant ID from the Authorization header in a request.
    
    Args:
        request: FastAPI request object
        jwt_config: JWT configuration
        raise_exceptions: If True, raises exceptions for invalid tokens
    
    Returns:
        Extracted tenant ID or None if extraction failed and raise_exceptions=False
        
    Raises:
        HTTPException: If authorization header is missing or invalid
        ValueError: If token validation fails and raise_exceptions=True
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        if raise_exceptions:
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        return None
        
    token = auth_header.replace("Bearer ", "")
    
    try:
        return extract_tenant_id(token, jwt_config, raise_exceptions)
    except ValueError as e:
        if raise_exceptions:
            raise HTTPException(status_code=401, detail=str(e))
        return None
