import json
import os
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest


ARTIFACT_DIR = Path("output/e2e-artifacts")


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.skip(f"Variável de ambiente obrigatória ausente: {name}")
    return value


def _post_json(url: str, payload: dict, token: str | None = None):
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(url=url, data=data, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8")
            return resp.getcode(), json.loads(raw)
    except HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        body = json.loads(raw) if raw else {"status": "error", "error": str(e)}
        return e.code, body
    except URLError as e:
        return 0, {"status": "error", "error": f"Network error: {e}"}


def _save_artifact(name: str, payload: dict):
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _assert_consulta_contract(status_code: int, body: dict):
    assert status_code in (200, 400, 401, 403, 500)
    assert isinstance(body, dict)

    if status_code == 200:
        # Single: pessoa/beneficios/meta; Batch: resultados
        assert ("resultados" in body) or (
            all(k in body for k in ("pessoa", "beneficios", "meta"))
            or (body.get("status") == "error" and "error" in body)
        )
    else:
        # Em 400, a API pode devolver status=invalid (erro de validação de entrada)
        # ou status=error (erro de payload/protocolo).
        if status_code == 400:
            assert body.get("status") in ("error", "invalid")
        else:
            assert body.get("status") == "error"
        assert "error" in body


@pytest.mark.e2e
def test_e2e_smoke_consulta_simples_e_refinada():
    base_url = _required_env("E2E_BASE_URL").rstrip("/")
    client_id = _required_env("E2E_CLIENT_ID")
    client_secret = _required_env("E2E_CLIENT_SECRET")
    consulta_base = _required_env("E2E_CONSULTA_BASE")
    consulta_refinada = os.getenv("E2E_CONSULTA_REFINADA", consulta_base).strip() or consulta_base

    now = datetime.now(timezone.utc).isoformat()

    token_status, token_body = _post_json(
        f"{base_url}/api/token/",
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "bot:read",
        },
    )
    _save_artifact(
        "01_token",
        {
            "timestamp_utc": now,
            "status_code": token_status,
            "body": {k: v for k, v in token_body.items() if k != "access_token"},
        },
    )
    assert token_status == 200
    assert "access_token" in token_body

    access_token = token_body["access_token"]

    start_false = datetime.now(timezone.utc)
    start_true = datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_false = executor.submit(
            _post_json,
            f"{base_url}/api/consulta/",
            {"consulta": consulta_base, "refinar_busca": False},
            access_token,
        )
        future_true = executor.submit(
            _post_json,
            f"{base_url}/api/consulta/",
            {"consulta": consulta_refinada, "refinar_busca": True},
            access_token,
        )
        status_false, body_false = future_false.result()
        end_false = datetime.now(timezone.utc)
        status_true, body_true = future_true.result()
        end_true = datetime.now(timezone.utc)

    _save_artifact(
        "02_consulta_refinar_false",
        {
            "timestamp_utc_inicio": start_false.isoformat(),
            "timestamp_utc_fim": end_false.isoformat(),
            "duracao_ms": int((end_false - start_false).total_seconds() * 1000),
            "payload": {"consulta": consulta_base, "refinar_busca": False},
            "status_code": status_false,
            "body": body_false,
        },
    )
    _assert_consulta_contract(status_false, body_false)
    _save_artifact(
        "03_consulta_refinar_true",
        {
            "timestamp_utc_inicio": start_true.isoformat(),
            "timestamp_utc_fim": end_true.isoformat(),
            "duracao_ms": int((end_true - start_true).total_seconds() * 1000),
            "payload": {"consulta": consulta_refinada, "refinar_busca": True},
            "status_code": status_true,
            "body": body_true,
        },
    )
    _assert_consulta_contract(status_true, body_true)

    _save_artifact(
        "04_resumo_concorrencia",
        {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "modo_execucao": "concorrente",
            "chamadas": [
                {
                    "nome": "consulta_refinar_false",
                    "status_code": status_false,
                    "status_body": body_false.get("status"),
                    "duracao_ms": int((end_false - start_false).total_seconds() * 1000),
                },
                {
                    "nome": "consulta_refinar_true",
                    "status_code": status_true,
                    "status_body": body_true.get("status"),
                    "duracao_ms": int((end_true - start_true).total_seconds() * 1000),
                },
            ],
        },
    )
