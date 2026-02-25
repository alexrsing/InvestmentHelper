import jwt
from fastapi import HTTPException, status

from .config import settings

# JWKS client — caches Clerk's public keys automatically
_jwks_client = jwt.PyJWKClient(settings.CLERK_JWKS_URL, cache_keys=True)


def decode_token(token: str) -> dict:
    """Decode and validate a Clerk-issued JWT using JWKS."""
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.CLERK_ISSUER,
            audience=settings.CLERK_AUDIENCE,
            options={"require": ["exp", "sub", "iss"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
