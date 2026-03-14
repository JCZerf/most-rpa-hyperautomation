import time
from typing import Tuple, Optional, Dict, Any, List

import jwt
from django.conf import settings
from jwt import InvalidTokenError, ExpiredSignatureError


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
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token, exp


def validate_token(token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
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
