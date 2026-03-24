import json
import logging
from contextvars import ContextVar, Token
from typing import Any

_id_consulta_ctx: ContextVar[str] = ContextVar("id_consulta", default="-")


def bind_id_consulta(id_consulta: str) -> Token:
    return _id_consulta_ctx.set(id_consulta or "-")


def reset_id_consulta(token: Token) -> None:
    _id_consulta_ctx.reset(token)


def current_id_consulta() -> str:
    return _id_consulta_ctx.get()


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "id_consulta": fields.pop("id_consulta", current_id_consulta()),
        **fields,
    }
    logger.log(level, json.dumps(payload, ensure_ascii=False, default=str))
