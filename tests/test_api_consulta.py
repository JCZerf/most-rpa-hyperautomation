import pytest
from rest_framework.test import APIClient


@pytest.fixture
def client(settings, monkeypatch):
    settings.OAUTH_CLIENT_ID = "client-id"
    settings.OAUTH_CLIENT_SECRET = "client-secret"
    settings.SECRET_KEY = "test-secret-1234567890abcdef1234567890abcdef"
    settings.API_MASTER_KEY = "test-master-key-1234567890abcdef1234567890"
    settings.API_TOKEN_TTL = 600
    settings.OAUTH_AUDIENCE = "most-rpa-api"

    api_client = APIClient()

    # Emite token usando o endpoint real
    resp = api_client.post(
        "/api/token/",
        data={"grant_type": "client_credentials", "client_id": "client-id", "client_secret": "client-secret"},
        format="json",
    )
    token = resp.json()["access_token"]

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # mock do bot para não abrir navegador
    return api_client


def test_consulta_single_ok(client):
    # Mock para não abrir navegador
    def fake_run(self):
        return {"status": "ok", "pessoa": {"nome": "Teste"}, "beneficios": []}
    from bot import scraper
    original_run = scraper.TransparencyBot.run
    scraper.TransparencyBot.run = fake_run

    resp = client.post("/api/consulta/", data={"consulta": "FULANO TESTE", "refinar_busca": False}, format="json")
    scraper.TransparencyBot.run = original_run
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") in (None, "ok")


def test_consulta_batch_limit(client):
    payload = {"consultas": ["04031769644", "12345678901", "11111111111", "22222222222"], "refinar_busca": False}
    resp = client.post("/api/consulta/", data=payload, format="json")
    assert resp.status_code == 400
    assert "Máximo" in resp.json().get("error", "")


def test_consulta_invalid_input(client):
    # sem mock: validação deve barrar antes de rodar bot
    resp = client.post("/api/consulta/", data={"consulta": "123ABC"}, format="json")
    assert resp.status_code == 400
    data = resp.json()
    assert data.get("status") == "invalid"


def test_consulta_missing_token():
    api_client = APIClient()
    resp = api_client.post("/api/consulta/", data={"consulta": "FULANO"}, format="json")
    assert resp.status_code == 401


def test_consulta_insufficient_scope(settings):
    settings.OAUTH_CLIENT_ID = "client-id"
    settings.OAUTH_CLIENT_SECRET = "client-secret"
    settings.SECRET_KEY = "test-secret-1234567890abcdef1234567890abcdef"
    settings.API_MASTER_KEY = "test-master-key-1234567890abcdef1234567890"
    settings.OAUTH_AUDIENCE = "most-rpa-api"
    api_client = APIClient()
    resp_token = api_client.post(
        "/api/token/",
        data={"grant_type": "client_credentials", "client_id": "client-id", "client_secret": "client-secret", "scope": "read-only"},
        format="json",
    )
    token = resp_token.json()["access_token"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    resp = api_client.post("/api/consulta/", data={"consulta": "FULANO"}, format="json")
    assert resp.status_code == 403


def test_consulta_single_invalid_from_bot_returns_400(client, monkeypatch):
    def fake_run_single(consulta_param, refine_param):
        return {"status": "invalid", "error": "entrada invalida", "consulta": consulta_param}

    monkeypatch.setattr("api.views._run_single", fake_run_single)
    resp = client.post("/api/consulta/", data={"consulta": "FULANO TESTE", "refinar_busca": False}, format="json")
    assert resp.status_code == 400
    data = resp.json()
    assert data["status"] == "invalid"
    assert "error" in data


def test_consulta_single_exception_returns_500(client, monkeypatch):
    def fake_run_single(consulta_param, refine_param):
        raise RuntimeError("falha interna")

    monkeypatch.setattr("api.views._run_single", fake_run_single)
    resp = client.post("/api/consulta/", data={"consulta": "FULANO TESTE", "refinar_busca": False}, format="json")
    assert resp.status_code == 500
    data = resp.json()
    assert data["status"] == "error"
    assert "falha interna" in data["error"]


def test_consulta_single_refinar_busca_true_is_forwarded(client, monkeypatch):
    calls = []

    def fake_run_single(consulta_param, refine_param):
        calls.append({"consulta": consulta_param, "refinar_busca": refine_param})
        return {"status": "ok", "pessoa": {"nome": "Teste"}, "beneficios": []}

    monkeypatch.setattr("api.views._run_single", fake_run_single)
    resp = client.post("/api/consulta/", data={"consulta": "FULANO TESTE", "refinar_busca": True}, format="json")
    assert resp.status_code == 200
    assert len(calls) == 1
    assert calls[0]["refinar_busca"] is True


def test_consulta_itens_refinar_busca_default_false_and_true_override(client, monkeypatch):
    calls = []

    def fake_run_single(consulta_param, refine_param):
        calls.append({"consulta": consulta_param, "refinar_busca": refine_param})
        return {"status": "ok", "pessoa": {"nome": consulta_param}, "beneficios": []}

    monkeypatch.setattr("api.views._run_single", fake_run_single)
    payload = {
        "itens": [
            {"consulta": "A LIDA PEREIRA FIALHO"},
            {"consulta": "A ANNE CHRISTINE SILVA RIBEIRO", "refinar_busca": True},
        ]
    }
    resp = client.post("/api/consulta/", data=payload, format="json")
    assert resp.status_code == 200
    assert len(calls) == 2
    assert calls[0]["refinar_busca"] is False
    assert calls[1]["refinar_busca"] is True


def test_consulta_missing_param_returns_json_error(client):
    resp = client.post("/api/consulta/", data={"refinar_busca": True}, format="json")
    assert resp.status_code == 400
    data = resp.json()
    assert data["status"] == "error"
    assert "consulta" in data["error"]


def test_consulta_batch_marks_error_status_item(client, monkeypatch):
    def fake_run_single(consulta_param, refine_param):
        return {"status": "error", "error": "falha de negocio"}

    monkeypatch.setattr("api.views._run_single", fake_run_single)
    payload = {"consultas": ["04031769644"], "refinar_busca": False}
    resp = client.post("/api/consulta/", data=payload, format="json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resultados"][0]["status"] == "error"


def test_consulta_itens_missing_consulta_preserva_ordem(client, monkeypatch):
    def fake_run_single(consulta_param, refine_param):
        return {"status": "ok", "pessoa": {"consulta": consulta_param}, "beneficios": [], "meta": {}}

    monkeypatch.setattr("api.views._run_single", fake_run_single)
    payload = {
        "itens": [
            {"consulta": "A LIDA PEREIRA FIALHO"},
            {},
            {"consulta": "A ANNE CHRISTINE SILVA RIBEIRO", "refinar_busca": True},
        ]
    }
    resp = client.post("/api/consulta/", data=payload, format="json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resultados"][0]["status"] == "ok"
    assert data["resultados"][0]["consulta"] == "A LIDA PEREIRA FIALHO"
    assert data["resultados"][1]["status"] == "error"
    assert "ausente" in data["resultados"][1]["error"]
    assert data["resultados"][2]["status"] == "ok"
    assert data["resultados"][2]["consulta"] == "A ANNE CHRISTINE SILVA RIBEIRO"


def test_consulta_single_refinar_busca_string_false(client, monkeypatch):
    calls = []

    def fake_run_single(consulta_param, refine_param):
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
