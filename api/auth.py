import time
from typing import Tuple, Optional, Dict, Any, List

import jwt
from django.conf import settings
from jwt import InvalidTokenError, ExpiredSignatureError


def _get_signing_key() -> str:
    """
    Returns the symmetric key used to sign/validate JWTs.
    Prefers API_MASTER_KEY; falls back to SECRET_KEY for backward compatibility.
    """
    key = settings.API_MASTER_KEY or settings.SECRET_KEY
    if not key:
        raise ValueError("API_MASTER_KEY (or SECRET_KEY) must be set to sign JWTs.")
    if len(key) < 32:
        # PyJWT emite warning; garantimos requisito mínimo do RFC 7518.
        raise ValueError("API_MASTER_KEY must be at least 32 characters for HS256.")
    return key


def issue_token(subject: str, ttl_seconds: int, scope: str, audience: str) -> Tuple[str, int]:
    exp = int(time.time()) + ttl_seconds
    payload = {
        "sub": subject,
        "exp": exp,
        "iat": int(time.time()),
        "scope": scope,
        "aud": audience,
        "iss": "most-rpa-auth",
    }
    token = jwt.encode(payload, _get_signing_key(), algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token, exp


def validate_token(token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    try:
        payload = jwt.decode(
            token,
            _get_signing_key(),
            algorithms=["HS256"],
            audience=settings.OAUTH_AUDIENCE,
        )
        return True, payload
    except ExpiredSignatureError:
        return False, None
    except InvalidTokenError:
        return False, None


def scope_allows(payload: Dict[str, Any], needed: List[str]) -> bool:
    scope_str = payload.get("scope", "")
    scopes = scope_str.split()
    return all(s in scopes for s in needed)
