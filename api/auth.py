import time
from threading import Lock
from typing import Tuple, Optional, Dict, Any, List
from uuid import uuid4

import jwt
from django.conf import settings
from jwt import InvalidTokenError, ExpiredSignatureError


_USED_TOKEN_JTIS: Dict[str, int] = {}
_USED_TOKEN_JTIS_LOCK = Lock()


def _get_signing_key() -> str:
    key = settings.API_MASTER_KEY
    if not key:
        raise ValueError("API_MASTER_KEY must be set to sign JWTs.")
    if len(key) < 32:
        # PyJWT emite warning; garantimos requisito mínimo do RFC 7518.
        raise ValueError("API_MASTER_KEY must be at least 32 characters for HS256.")
    return key


def issue_token(subject: str, ttl_seconds: int, scope: str, audience: str) -> Tuple[str, int]:
    now = int(time.time())
    exp = now + ttl_seconds
    payload = {
        "sub": subject,
        "exp": exp,
        "iat": now,
        "jti": str(uuid4()),
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


def consume_token_once(payload: Dict[str, Any]) -> bool:
    """
    Marca o token como consumido no primeiro uso da rota protegida.
    Retorna False quando já foi usado anteriormente ou quando o payload é inválido.
    """
    jti = str(payload.get("jti") or "").strip()
    if not jti:
        return False

    exp_raw = payload.get("exp")
    try:
        exp = int(exp_raw)
    except (TypeError, ValueError):
        return False

    now = int(time.time())
    if exp <= now:
        return False

    with _USED_TOKEN_JTIS_LOCK:
        expirados = [item_jti for item_jti, item_exp in _USED_TOKEN_JTIS.items() if item_exp <= now]
        for item_jti in expirados:
            _USED_TOKEN_JTIS.pop(item_jti, None)

        if jti in _USED_TOKEN_JTIS:
            return False

        _USED_TOKEN_JTIS[jti] = exp
        return True
