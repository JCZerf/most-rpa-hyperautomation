import os

import pytest
from rest_framework.test import APIClient


TEST_OAUTH_CLIENT_ID = os.getenv("TEST_OAUTH_CLIENT_ID", "test-client-id")
TEST_OAUTH_CLIENT_SECRET = os.getenv("TEST_OAUTH_CLIENT_SECRET", "test-client-secret")
TEST_DJANGO_SECRET_KEY = os.getenv(
    "TEST_DJANGO_SECRET_KEY",
    "test-secret-1234567890abcdef1234567890abcdef",
)
TEST_API_MASTER_KEY = os.getenv(
    "TEST_API_MASTER_KEY",
    "test-master-key-1234567890abcdef1234567890",
)
TEST_OAUTH_AUDIENCE = os.getenv("TEST_OAUTH_AUDIENCE", "most-rpa-api")
TEST_API_TOKEN_TTL = int(os.getenv("TEST_API_TOKEN_TTL", "600"))


@pytest.fixture
def client(settings):
    settings.OAUTH_CLIENT_ID = TEST_OAUTH_CLIENT_ID
    settings.OAUTH_CLIENT_SECRET = TEST_OAUTH_CLIENT_SECRET
    settings.SECRET_KEY = TEST_DJANGO_SECRET_KEY
    settings.API_MASTER_KEY = TEST_API_MASTER_KEY
    settings.API_TOKEN_TTL = TEST_API_TOKEN_TTL
    settings.OAUTH_AUDIENCE = TEST_OAUTH_AUDIENCE

    api_client = APIClient()
    resp = api_client.post(
        "/api/token/",
        data={
            "grant_type": "client_credentials",
            "client_id": TEST_OAUTH_CLIENT_ID,
            "client_secret": TEST_OAUTH_CLIENT_SECRET,
        },
        format="json",
    )
    token = resp.json()["access_token"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


def test_consulta_single_ok(client, monkeypatch):
    monkeypatch.setattr(
        "api.views._run_single",
        lambda consulta_param, refine_param, incluir_base64: {
            "status": "ok",
            "pessoa": {"nome": "Teste"},
            "beneficios": [],
        },
    )
    resp = client.post("/api/consulta/", data={"consulta": "FULANO TESTE", "refinar_busca": False}, format="json")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") in (None, "ok")


def test_consulta_batch_sem_limite_fixo(client, monkeypatch):
    payload = {"consultas": [f"CONSULTA-{i}" for i in range(9)], "refinar_busca": False}

    def fake_run_batch(itens, incluir_base64):
        return {
            "resultados": [
                {
                    "indice_entrada": item["indice_entrada"],
                    "consulta": item["consulta"],
                    "duracao_segundos": 0.01,
                    "resultado": {"status": "ok", "pessoa": {"consulta": item["consulta"]}, "beneficios": []},
                }
                for item in itens
            ],
            "meta_execucao": {"max_browsers": 1, "max_consultas_por_browser": 4, "blocos_fila": 3},
        }

    monkeypatch.setattr("api.views._run_batch", fake_run_batch)
    resp = client.post("/api/consulta/", data=payload, format="json")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["resultados"]) == 9
    assert data["meta_execucao"]["blocos_fila"] == 3


def test_consulta_invalid_input(client):
    resp = client.post("/api/consulta/", data={"consulta": "123ABC"}, format="json")
    assert resp.status_code == 400
    data = resp.json()
    assert data.get("status") == "invalid"


def test_consulta_missing_token():
    api_client = APIClient()
    resp = api_client.post("/api/consulta/", data={"consulta": "FULANO"}, format="json")
    assert resp.status_code == 401


def test_consulta_token_uso_unico_exige_nova_autenticacao(settings, monkeypatch):
    settings.OAUTH_CLIENT_ID = TEST_OAUTH_CLIENT_ID
    settings.OAUTH_CLIENT_SECRET = TEST_OAUTH_CLIENT_SECRET
    settings.SECRET_KEY = TEST_DJANGO_SECRET_KEY
    settings.API_MASTER_KEY = TEST_API_MASTER_KEY
    settings.OAUTH_AUDIENCE = TEST_OAUTH_AUDIENCE

    monkeypatch.setattr(
        "api.views._run_single",
        lambda consulta_param, refine_param, incluir_base64: {"status": "ok", "pessoa": {"nome": "Teste"}, "beneficios": []},
    )

    api_client = APIClient()
    token_resp = api_client.post(
        "/api/token/",
        data={
            "grant_type": "client_credentials",
            "client_id": TEST_OAUTH_CLIENT_ID,
            "client_secret": TEST_OAUTH_CLIENT_SECRET,
        },
        format="json",
    )
    assert token_resp.status_code == 200

    token = token_resp.json()["access_token"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    resp_1 = api_client.post("/api/consulta/", data={"consulta": "FULANO TESTE"}, format="json")
    assert resp_1.status_code == 200

    resp_2 = api_client.post("/api/consulta/", data={"consulta": "FULANO TESTE"}, format="json")
    assert resp_2.status_code == 401
    assert resp_2.json()["status"] == "error"


def test_consulta_insufficient_scope(settings, monkeypatch):
    settings.OAUTH_CLIENT_ID = TEST_OAUTH_CLIENT_ID
    settings.OAUTH_CLIENT_SECRET = TEST_OAUTH_CLIENT_SECRET
    settings.SECRET_KEY = TEST_DJANGO_SECRET_KEY
    settings.API_MASTER_KEY = TEST_API_MASTER_KEY
    settings.OAUTH_AUDIENCE = TEST_OAUTH_AUDIENCE
    api_client = APIClient()
    resp_token = api_client.post(
        "/api/token/",
        data={
            "grant_type": "client_credentials",
            "client_id": TEST_OAUTH_CLIENT_ID,
            "client_secret": TEST_OAUTH_CLIENT_SECRET,
            "scope": "bot:read",
        },
        format="json",
    )
    assert resp_token.status_code == 200
    token = resp_token.json()["access_token"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    monkeypatch.setattr("api.views.scope_allows", lambda claims, required: False)
    resp = api_client.post("/api/consulta/", data={"consulta": "FULANO"}, format="json")
    assert resp.status_code == 403


def test_consulta_single_invalid_from_bot_returns_400(client, monkeypatch):
    monkeypatch.setattr(
        "api.views._run_single",
        lambda consulta_param, refine_param, incluir_base64: {
            "status": "invalid",
            "error": "entrada invalida",
            "consulta": consulta_param,
        },
    )
    resp = client.post("/api/consulta/", data={"consulta": "FULANO TESTE", "refinar_busca": False}, format="json")
    assert resp.status_code == 400
    assert resp.json()["status"] == "invalid"


def test_consulta_single_exception_returns_500(client, monkeypatch):
    def fake_run_single(consulta_param, refine_param, incluir_base64):
        raise RuntimeError("falha interna")

    monkeypatch.setattr("api.views._run_single", fake_run_single)
    resp = client.post("/api/consulta/", data={"consulta": "FULANO TESTE", "refinar_busca": False}, format="json")
    assert resp.status_code == 500
    data = resp.json()
    assert data["status"] == "error"
    assert "falha interna" in data["error"]


def test_consulta_single_refinar_busca_true_is_forwarded(client, monkeypatch):
    calls = []

    def fake_run_single(consulta_param, refine_param, incluir_base64):
        calls.append({"consulta": consulta_param, "refinar_busca": refine_param, "incluir_base64": incluir_base64})
        return {"status": "ok", "pessoa": {"nome": "Teste"}, "beneficios": []}

    monkeypatch.setattr("api.views._run_single", fake_run_single)
    resp = client.post("/api/consulta/", data={"consulta": "FULANO TESTE", "refinar_busca": True}, format="json")
    assert resp.status_code == 200
    assert len(calls) == 1
    assert calls[0]["refinar_busca"] is True


def test_consulta_single_incluir_base64_false_is_forwarded(client, monkeypatch):
    calls = []

    def fake_run_single(consulta_param, refine_param, incluir_base64):
        calls.append(incluir_base64)
        return {"status": "ok", "pessoa": {"consulta": consulta_param}, "beneficios": [], "meta": {}}

    monkeypatch.setattr("api.views._run_single", fake_run_single)
    resp = client.post(
        "/api/consulta/",
        data={"consulta": "FULANO TESTE", "incluir_base64": False},
        format="json",
    )
    assert resp.status_code == 200
    assert calls == [False]


def test_consulta_itens_refinar_busca_default_false_and_true_override(client, monkeypatch):
    captured = {}

    def fake_run_batch(itens, incluir_base64):
        captured["itens"] = itens
        return {
            "resultados": [
                {
                    "indice_entrada": item["indice_entrada"],
                    "consulta": item["consulta"],
                    "duracao_segundos": 0.01,
                    "resultado": {"status": "ok", "pessoa": {"nome": item["consulta"]}, "beneficios": []},
                }
                for item in itens
            ],
            "meta_execucao": {},
        }

    monkeypatch.setattr("api.views._run_batch", fake_run_batch)
    payload = {
        "itens": [
            {"consulta": "A LIDA PEREIRA FIALHO"},
            {"consulta": "A ANNE CHRISTINE SILVA RIBEIRO", "refinar_busca": True},
        ]
    }
    resp = client.post("/api/consulta/", data=payload, format="json")
    assert resp.status_code == 200
    assert len(captured["itens"]) == 2
    assert captured["itens"][0]["refinar_busca"] is False
    assert captured["itens"][1]["refinar_busca"] is True


def test_consulta_missing_param_returns_json_error(client):
    resp = client.post("/api/consulta/", data={"refinar_busca": True}, format="json")
    assert resp.status_code == 400
    data = resp.json()
    assert data["status"] == "error"
    assert "consulta" in data["error"]


def test_consulta_batch_marks_error_status_item(client, monkeypatch):
    def fake_run_batch(itens, incluir_base64):
        item = itens[0]
        return {
            "resultados": [
                {
                    "indice_entrada": item["indice_entrada"],
                    "consulta": item["consulta"],
                    "duracao_segundos": 0.01,
                    "resultado": {"status": "error", "error": "falha de negocio"},
                }
            ],
            "meta_execucao": {},
        }

    monkeypatch.setattr("api.views._run_batch", fake_run_batch)
    payload = {"consultas": ["04031769644"], "refinar_busca": False}
    resp = client.post("/api/consulta/", data=payload, format="json")
    assert resp.status_code == 502
    data = resp.json()
    assert data["resultados"][0]["status"] == "error"


def test_consulta_itens_missing_consulta_preserva_ordem(client, monkeypatch):
    def fake_run_batch(itens, incluir_base64):
        return {
            "resultados": [
                {
                    "indice_entrada": item["indice_entrada"],
                    "consulta": item["consulta"],
                    "duracao_segundos": 0.01,
                    "resultado": {"status": "ok", "pessoa": {"consulta": item["consulta"]}, "beneficios": [], "meta": {}},
                }
                for item in itens
            ],
            "meta_execucao": {},
        }

    monkeypatch.setattr("api.views._run_batch", fake_run_batch)
    payload = {
        "itens": [
            {"consulta": "A LIDA PEREIRA FIALHO"},
            {},
            {"consulta": "A ANNE CHRISTINE SILVA RIBEIRO", "refinar_busca": True},
        ]
    }
    resp = client.post("/api/consulta/", data=payload, format="json")
    assert resp.status_code == 207
    data = resp.json()
    assert data["resultados"][0]["status"] == "ok"
    assert data["resultados"][1]["status"] == "error"
    assert "ausente" in data["resultados"][1]["error"]
    assert data["resultados"][2]["status"] == "ok"


def test_consulta_single_refinar_busca_string_false(client, monkeypatch):
    calls = []

    def fake_run_single(consulta_param, refine_param, incluir_base64):
        calls.append(refine_param)
        return {"status": "ok", "pessoa": {"consulta": consulta_param}, "beneficios": [], "meta": {}}

    monkeypatch.setattr("api.views._run_single", fake_run_single)
    resp = client.post(
        "/api/consulta/",
        data={"consulta": "FULANO TESTE", "refinar_busca": "false"},
        format="multipart",
    )
    assert resp.status_code == 200
    assert calls == [False]


def test_consulta_single_error_from_bot_returns_502(client, monkeypatch):
    monkeypatch.setattr(
        "api.views._run_single",
        lambda consulta_param, refine_param, incluir_base64: {"status": "error", "error": "falha no portal"},
    )
    resp = client.post("/api/consulta/", data={"consulta": "FULANO TESTE"}, format="json")
    assert resp.status_code == 502
    assert resp.json()["status"] == "error"


def test_consulta_single_error_retries_once_and_recovers(client, monkeypatch):
    calls = []

    def fake_run_single(consulta_param, refine_param, incluir_base64):
        calls.append(consulta_param)
        if len(calls) == 1:
            return {"status": "error", "error": "falha no portal"}
        return {"status": "ok", "pessoa": {"consulta": consulta_param}, "beneficios": [], "meta": {}}

    monkeypatch.setattr("api.views._run_single", fake_run_single)
    resp = client.post("/api/consulta/", data={"consulta": "FULANO TESTE"}, format="json")
    assert resp.status_code == 200
    assert calls == ["FULANO TESTE", "FULANO TESTE"]
    assert resp.json()["status"] == "ok"


def test_consulta_single_invalid_does_not_retry(client, monkeypatch):
    calls = []

    def fake_run_single(consulta_param, refine_param, incluir_base64):
        calls.append(consulta_param)
        return {"status": "invalid", "error": "entrada invalida", "consulta": consulta_param}

    monkeypatch.setattr("api.views._run_single", fake_run_single)
    resp = client.post("/api/consulta/", data={"consulta": "123ABC"}, format="json")
    assert resp.status_code == 400
    assert calls == ["123ABC"]
    assert resp.json()["status"] == "invalid"


def test_consulta_single_not_found_returns_200(client, monkeypatch):
    monkeypatch.setattr(
        "api.views._run_single",
        lambda consulta_param, refine_param, incluir_base64: {
            "status": "not_found",
            "pessoa": {"consulta": consulta_param, "nome": "N/A"},
            "beneficios": [],
            "meta": {"resultados_encontrados": 0, "mensagem": "Nenhum encontrado"},
        },
    )
    resp = client.post("/api/consulta/", data={"consulta": "FULANO TESTE"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_found"


def test_consulta_batch_partial_success_returns_207(client, monkeypatch):
    def fake_run_batch(itens, incluir_base64):
        saida = []
        for item in itens:
            status = "ok" if item["consulta"] == "A" else "error"
            payload = {"status": status, "pessoa": {"nome": item["consulta"]}, "beneficios": []}
            if status == "error":
                payload = {"status": "error", "error": "falha"}
            saida.append(
                {
                    "indice_entrada": item["indice_entrada"],
                    "consulta": item["consulta"],
                    "duracao_segundos": 0.01,
                    "resultado": payload,
                }
            )
        return {"resultados": saida, "meta_execucao": {}}

    monkeypatch.setattr("api.views._run_batch", fake_run_batch)
    payload = {"consultas": ["A", "B"], "refinar_busca": False}
    resp = client.post("/api/consulta/", data=payload, format="json")
    assert resp.status_code == 207
    data = resp.json()
    assert {item["status"] for item in data["resultados"]} == {"ok", "error"}


def test_consulta_batch_retries_only_error_items_once(client, monkeypatch):
    calls = []

    def fake_run_batch(itens, incluir_base64):
        consultas = [item["consulta"] for item in itens]
        calls.append(consultas)

        saida = []
        for item in itens:
            consulta = item["consulta"]
            if consulta == "A":
                resultado = {"status": "ok", "pessoa": {"nome": consulta}, "beneficios": [], "meta": {}}
            elif consulta == "B" and len(calls) == 1:
                resultado = {"status": "error", "error": "falha transitória"}
            elif consulta == "B":
                resultado = {"status": "ok", "pessoa": {"nome": consulta}, "beneficios": [], "meta": {}}
            else:
                resultado = {
                    "status": "invalid",
                    "error": "entrada invalida",
                    "pessoa": {"consulta": consulta, "nome": "N/A", "cpf": "N/A", "localidade": "N/A"},
                    "beneficios": [],
                    "meta": {},
                }

            saida.append(
                {
                    "indice_entrada": item["indice_entrada"],
                    "consulta": consulta,
                    "duracao_segundos": 0.01,
                    "resultado": resultado,
                }
            )
        return {"resultados": saida, "meta_execucao": {"total_consultas": len(itens)}}

    monkeypatch.setattr("api.views._run_batch", fake_run_batch)
    payload = {"consultas": ["A", "B", "123ABC"], "refinar_busca": False}
    resp = client.post("/api/consulta/", data=payload, format="json")
    assert resp.status_code == 207
    assert calls == [["A", "B", "123ABC"], ["B"]]

    data = resp.json()
    assert data["meta_execucao"]["total_consultas"] == 3
    assert [item["status"] for item in data["resultados"]] == ["ok", "ok", "invalid"]
