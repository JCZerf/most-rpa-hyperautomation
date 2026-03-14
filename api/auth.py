import time
from typing import Tuple, Optional, Dict, Any

import jwt
from django.conf import settings
from jwt import InvalidTokenError, ExpiredSignatureError


def issue_token(subject: str, ttl_seconds: int) -> Tuple[str, int]:
    exp = int(time.time()) + ttl_seconds
    payload = {
        "sub": subject,
        "exp": exp,
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    # PyJWT may return str or bytes depending on version; normalize to str
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token, exp


def validate_token(token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return True, payload
    except ExpiredSignatureError:
        return False, None
    except InvalidTokenError:
        return False, None
