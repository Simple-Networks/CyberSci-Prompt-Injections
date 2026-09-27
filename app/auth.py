"""HS256 admin-JWT issuing and verification.

Deliberately minimal: the signing secret is weak and configurable, so JWT attacks
(secret cracking, tampering) are part of the lesson. Route 3 relies on ``verify_admin_token``.
"""

from datetime import datetime, timedelta, timezone

import jwt

from .config import get_settings


class AuthError(Exception):
    """Raised when a token is missing, malformed, expired, or lacks admin role."""


def create_admin_token() -> str:
    """Mint an HS256 JWT carrying ``role: admin``."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "admin-user",
        "role": "admin",
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + timedelta(seconds=settings.jwt_ttl_seconds),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_alg)


def verify_admin_token(token: str) -> dict:
    """Decode and validate a token, requiring the admin role. Returns the claims."""
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_alg],
            issuer=settings.jwt_issuer,
        )
    except jwt.PyJWTError as exc:
        raise AuthError(f"invalid token: {exc}") from exc

    if claims.get("role") != "admin":
        raise AuthError("token does not carry the 'admin' role")
    return claims
