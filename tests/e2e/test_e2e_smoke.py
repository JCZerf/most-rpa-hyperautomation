import json
import os
import math
import warnings
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest


ARTIFACT_DIR = Path("output/e2e-artifacts")
E2E_HTTP_TIMEOUT_SECONDS = 900


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.skip(f"Variável de ambiente obrigatória ausente: {name}")
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw.strip())
    except (TypeError, ValueError):
        return default


def _batch_targets_from_env() -> list[str]:
    raw = os.getenv("E2E_BATCH_TARGETS", "").strip()
    if not raw:
        pytest.skip("Variável obrigatória ausente para batch: E2E_BATCH_TARGETS")

    targets = [item.strip() for item in raw.split(";") if item.strip()]
    if len(targets) < 2:
        pytest.skip("Batch exige pelo menos 2 alvos em E2E_BATCH_TARGETS")
    # Smoke: limita carga de batch para manter tempo de execução previsível no CI.
    return targets[:8]


def _build_mixed_batch_payload(targets: list[str]) -> tuple[dict, dict]:
    total = len(targets)
    metade_false = total // 2
    itens = []
    for idx, consulta in enumerate(targets):
        itens.append({"consulta": consulta, "refinar_busca": bool(idx >= metade_false)})
    return {"itens": itens, "incluir_base64": False}, {
        "modo_payload": "batch_itens_misto",
        "total_consultas": total,
        "total_refinar_false": metade_false,
        "total_refinar_true": total - metade_false,
        "incluir_base64": False,
    }


def _build_mixed_batch_payload_with_size(targets_pool: list[str], total: int) -> tuple[dict, dict]:
    if total < 1:
        pytest.fail("Tamanho de lote inválido")
    selected = [targets_pool[idx % len(targets_pool)] for idx in range(total)]
    return _build_mixed_batch_payload(selected)


def _post_json(url: str, payload: dict, token: str | None = None):
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(url=url, data=data, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=E2E_HTTP_TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.getcode(), json.loads(raw)
            except json.JSONDecodeError:
                return resp.getcode(), {"status": "error", "error": raw or "Invalid JSON response"}
    except HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        try:
            body = json.loads(raw) if raw else {"status": "error", "error": str(e)}
        except json.JSONDecodeError:
            body = {"status": "error", "error": raw or str(e)}
        return e.code, body
    except URLError as e:
        return 0, {"status": "error", "error": f"Network error: {e}"}


def _save_artifact(name: str, payload: dict):
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _require_success_enabled() -> bool:
    return _env_bool("E2E_REQUIRE_SUCCESS", False)


def _issue_access_token(base_url: str, client_id: str, client_secret: str):
    return _post_json(
        f"{base_url}/api/token/",
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "bot:read",
        },
    )


def _assert_batch_limits_meta(body: dict, expected_total: int):
    meta = body.get("meta_execucao")
    assert isinstance(meta, dict), f"Resposta de lote sem meta_execucao: {body}"
    assert int(meta.get("total_consultas", -1)) == expected_total
    max_por_browser = int(meta.get("max_consultas_por_browser", 0))
    assert max_por_browser >= 1
    expected_blocos = math.ceil(expected_total / max_por_browser)
    assert int(meta.get("blocos_fila", -1)) == expected_blocos


def _batch_item_retry_meta(item: dict) -> dict:
    resultado = (item or {}).get("resultado")
    if not isinstance(resultado, dict):
        return {}
    meta = resultado.get("meta")
    if not isinstance(meta, dict):
        return {}
    retry = meta.get("retry")
    if isinstance(retry, dict):
        return retry
    return {}


def _summarize_batch_statuses(body: dict) -> dict:
    resultados = body.get("resultados")
    assert isinstance(resultados, list), f"Resposta de lote sem resultados para sumarizacao: {body}"

    counts = {"ok": 0, "not_found": 0, "invalid": 0, "error": 0, "unknown": 0}
    retry = {
        "itens_com_retry": 0,
        "recuperados_por_retry": 0,
        "erro_final_apos_retry": 0,
        "sucesso_sem_retry": 0,
        "sucesso_com_retry": 0,
    }
    for item in resultados:
        status_item = str((item or {}).get("status") or "").lower()
        if status_item in counts:
            counts[status_item] += 1
        else:
            counts["unknown"] += 1

        retry_meta = _batch_item_retry_meta(item)
        retry_acionado = bool(retry_meta.get("retry_acionado", False))
        recuperado_por_retry = bool(retry_meta.get("recuperado_por_retry", False))
        if retry_acionado:
            retry["itens_com_retry"] += 1
            if recuperado_por_retry:
                retry["recuperados_por_retry"] += 1
            elif status_item == "error":
                retry["erro_final_apos_retry"] += 1

        if status_item in ("ok", "not_found"):
            if retry_acionado and recuperado_por_retry:
                retry["sucesso_com_retry"] += 1
            else:
                retry["sucesso_sem_retry"] += 1

    total = len(resultados)
    success_count = counts["ok"] + counts["not_found"]
    success_rate = (success_count / total) if total else 0.0

    return {
        "total": total,
        "success_count": success_count,
        "success_rate": success_rate,
        "success_rate_basis": "final_status_after_retry",
        "counts": counts,
        "retry": retry,
    }


def _summarize_parallel_batch_results(resultados: list[tuple[int, dict]]) -> dict:
    total_items = 0
    success_count = 0
    counts = {"ok": 0, "not_found": 0, "invalid": 0, "error": 0, "unknown": 0}
    retry = {
        "itens_com_retry": 0,
        "recuperados_por_retry": 0,
        "erro_final_apos_retry": 0,
        "sucesso_sem_retry": 0,
        "sucesso_com_retry": 0,
    }
    response_codes: dict[str, int] = {}

    for status_code, body in resultados:
        response_codes[str(status_code)] = response_codes.get(str(status_code), 0) + 1
        if "resultados" not in body:
            continue
        resumo = _summarize_batch_statuses(body)
        total_items += resumo["total"]
        success_count += resumo["success_count"]
        for key, value in resumo["counts"].items():
            counts[key] += value
        for key, value in resumo["retry"].items():
            retry[key] += value

    success_rate = (success_count / total_items) if total_items else 0.0
    return {
        "total_items": total_items,
        "success_count": success_count,
        "success_rate": success_rate,
        "success_rate_basis": "final_status_after_retry",
        "counts": counts,
        "retry": retry,
        "response_codes": response_codes,
    }


def _assert_batch_item_contract(item: dict):
    assert isinstance(item, dict)
    assert "consulta" in item

    status_item = item.get("status")
    assert status_item in ("ok", "not_found", "invalid", "error")

    resultado = item.get("resultado")
    if status_item == "ok":
        assert isinstance(resultado, dict), f"Item de lote sem resultado estruturado: {item}"
        # No contrato real de batch, itens OK usam o status no envelope do item;
        # o payload interno normalmente nao repete `status`.
        assert resultado.get("status") in (None, "ok")
        assert all(k in resultado for k in ("pessoa", "beneficios", "meta"))
    elif status_item in ("not_found", "invalid"):
        assert isinstance(resultado, dict), f"Item de lote sem resultado estruturado: {item}"
        assert resultado.get("status") == status_item
        if status_item == "invalid":
            assert "error" in resultado
        else:
            assert all(k in resultado for k in ("pessoa", "beneficios", "meta"))
    else:
        assert ("error" in item) or isinstance(resultado, dict), f"Item de lote com erro sem detalhe: {item}"
        if isinstance(resultado, dict):
            assert resultado.get("status") == "error"
            assert "error" in resultado


def _assert_batch_consulta_contract(status_code: int, body: dict):
    assert status_code in (200, 207, 400, 502)
    resultados = body.get("resultados")
    assert isinstance(resultados, list), f"Resposta de lote sem resultados: {body}"
    meta = body.get("meta_execucao")
    assert isinstance(meta, dict), f"Resposta de lote sem meta_execucao: {body}"
    for item in resultados:
        _assert_batch_item_contract(item)


def _assert_consulta_contract(status_code: int, body: dict):
    assert status_code in (200, 207, 400, 401, 403, 500, 502)
    assert isinstance(body, dict)

    if "resultados" in body:
        _assert_batch_consulta_contract(status_code, body)
        return

    if status_code == 200:
        # Single: pessoa/beneficios/meta; Batch: resultados
        assert all(k in body for k in ("pessoa", "beneficios", "meta")) or (
            body.get("status") == "error" and "error" in body
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

    token_status_1, token_body_1 = _issue_access_token(base_url, client_id, client_secret)
    token_status_2, token_body_2 = _issue_access_token(base_url, client_id, client_secret)
    _save_artifact(
        "01_tokens",
        {
            "timestamp_utc": now,
            "token_1": {
                "status_code": token_status_1,
                "body": {k: v for k, v in token_body_1.items() if k != "access_token"},
            },
            "token_2": {
                "status_code": token_status_2,
                "body": {k: v for k, v in token_body_2.items() if k != "access_token"},
            },
        },
    )
    assert token_status_1 == 200
    assert token_status_2 == 200
    assert "access_token" in token_body_1
    assert "access_token" in token_body_2

    access_token_false = token_body_1["access_token"]
    access_token_true = token_body_2["access_token"]

    start_false = datetime.now(timezone.utc)
    start_true = datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_false = executor.submit(
            _post_json,
            f"{base_url}/api/consulta/",
            {"consulta": consulta_base, "refinar_busca": False},
            access_token_false,
        )
        future_true = executor.submit(
            _post_json,
            f"{base_url}/api/consulta/",
            {"consulta": consulta_refinada, "refinar_busca": True},
            access_token_true,
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

    if _require_success_enabled():
        assert status_false == 200, f"Consulta concorrente (refinar_busca=false) retornou {status_false}: {body_false}"
        assert status_true == 200, f"Consulta concorrente (refinar_busca=true) retornou {status_true}: {body_true}"
        assert body_false.get("status") != "invalid", f"Consulta base inválida: {body_false}"
        assert body_true.get("status") != "invalid", f"Consulta refinada inválida: {body_true}"


@pytest.mark.e2e
def test_e2e_smoke_lote_reage_a_limites_da_api():
    base_url = _required_env("E2E_BASE_URL").rstrip("/")
    client_id = _required_env("E2E_CLIENT_ID")
    client_secret = _required_env("E2E_CLIENT_SECRET")
    consultas_lote = _batch_targets_from_env()
    payload, payload_meta = _build_mixed_batch_payload(consultas_lote)

    token_status, token_body = _issue_access_token(base_url, client_id, client_secret)
    assert token_status == 200
    assert "access_token" in token_body

    status_code, body = _post_json(f"{base_url}/api/consulta/", payload, token_body["access_token"])

    _save_artifact(
        "05_lote_limites",
        {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "consultas_configuradas": consultas_lote,
            "payload_meta": payload_meta,
            "payload": payload,
            "status_code": status_code,
            "body": body,
        },
    )

    _assert_consulta_contract(status_code, body)
    if "resultados" in body:
        _assert_batch_limits_meta(body, expected_total=len(consultas_lote))


@pytest.mark.e2e
def test_e2e_smoke_lote_unico_8_alvos():
    base_url = _required_env("E2E_BASE_URL").rstrip("/")
    client_id = _required_env("E2E_CLIENT_ID")
    client_secret = _required_env("E2E_CLIENT_SECRET")
    consultas_lote = _batch_targets_from_env()
    payload, payload_meta = _build_mixed_batch_payload_with_size(consultas_lote, total=8)

    token_status, token_body = _issue_access_token(base_url, client_id, client_secret)
    assert token_status == 200
    assert "access_token" in token_body

    status_code, body = _post_json(f"{base_url}/api/consulta/", payload, token_body["access_token"])

    _save_artifact(
        "07_lote_8_alvos",
        {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "consultas_configuradas": consultas_lote,
            "payload_meta": payload_meta,
            "payload": payload,
            "status_code": status_code,
            "body": body,
        },
    )

    _assert_consulta_contract(status_code, body)
    if "resultados" in body:
        _assert_batch_limits_meta(body, expected_total=8)


@pytest.mark.e2e
def test_e2e_smoke_requisicoes_simultaneas_com_lotes():
    base_url = _required_env("E2E_BASE_URL").rstrip("/")
    client_id = _required_env("E2E_CLIENT_ID")
    client_secret = _required_env("E2E_CLIENT_SECRET")
    consultas_paralelo = _batch_targets_from_env()[:6]
    payload, payload_meta = _build_mixed_batch_payload(consultas_paralelo)
    # Ambiente atual: até 2 requisições simultâneas por instância.
    reqs_paralelas = 2

    tokens: list[str] = []
    for _ in range(reqs_paralelas):
        token_status, token_body = _issue_access_token(base_url, client_id, client_secret)
        assert token_status == 200
        assert "access_token" in token_body
        tokens.append(token_body["access_token"])
    started_at = datetime.now(timezone.utc)

    def _executar(token: str):
        return _post_json(f"{base_url}/api/consulta/", payload, token)

    with ThreadPoolExecutor(max_workers=reqs_paralelas) as executor:
        resultados = list(executor.map(_executar, tokens))

    ended_at = datetime.now(timezone.utc)

    respostas = []
    for idx, (status_code, body) in enumerate(resultados, start=1):
        resposta_payload = {"indice": idx, "status_code": status_code, "body": body}
        if "resultados" in body:
            resposta_payload["resumo_status"] = _summarize_batch_statuses(body)
        respostas.append(resposta_payload)

    resumo_execucao = _summarize_parallel_batch_results(resultados)

    _save_artifact(
        "06_requisicoes_simultaneas_lote",
        {
            "timestamp_utc_inicio": started_at.isoformat(),
            "timestamp_utc_fim": ended_at.isoformat(),
            "duracao_ms_total": int((ended_at - started_at).total_seconds() * 1000),
            "requisicoes_paralelas": reqs_paralelas,
            "lote_por_requisicao": len(consultas_paralelo),
            "consultas_configuradas": consultas_paralelo,
            "payload_meta": payload_meta,
            "payload": payload,
            "resumo_execucao": resumo_execucao,
            "respostas": respostas,
        },
    )

    for status_code, body in resultados:
        _assert_consulta_contract(status_code, body)
        if "resultados" in body:
            _assert_batch_limits_meta(body, expected_total=len(consultas_paralelo))

    if _require_success_enabled():
        min_success_rate = _env_float("E2E_BATCH_MIN_SUCCESS_RATE", 0.8)
        assert resumo_execucao["counts"]["invalid"] == 0, f"Lote concorrente teve itens invalidos: {resumo_execucao}"
        assert resumo_execucao["counts"]["unknown"] == 0, f"Lote concorrente teve itens com status desconhecido: {resumo_execucao}"
        assert resumo_execucao["success_rate"] >= min_success_rate, (
            f"Taxa de sucesso do lote concorrente abaixo do minimo "
            f"({resumo_execucao['success_rate']:.2%} < {min_success_rate:.2%}): {resumo_execucao}"
        )
        if resumo_execucao["success_rate"] < 1.0:
            warnings.warn(
                "Lote concorrente com sucesso parcial: "
                f"taxa_final={resumo_execucao['success_rate']:.2%}, "
                f"sucesso_com_retry={resumo_execucao['retry']['sucesso_com_retry']}, "
                f"erro_final_apos_retry={resumo_execucao['retry']['erro_final_apos_retry']}, "
                f"resumo={resumo_execucao}",
                stacklevel=2,
            )
