import pytest
from rest_framework.test import APIClient


@pytest.fixture
def client(settings, monkeypatch):
    settings.OAUTH_CLIENT_ID = "client-id"
    settings.OAUTH_CLIENT_SECRET = "client-secret"
    settings.SECRET_KEY = "test-secret-1234567890abcdef1234567890abcdef"
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

    resp = client.post("/api/consulta/", data={"consulta": "FULANO TESTE", "refine": False}, format="json")
    scraper.TransparencyBot.run = original_run
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") in (None, "ok")


def test_consulta_batch_limit(client):
    payload = {"consultas": ["04031769644", "12345678901", "11111111111", "22222222222"], "refine": False}
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
    resp = client.post("/api/consulta/", data={"consulta": "FULANO TESTE", "refine": False}, format="json")
    assert resp.status_code == 400
    data = resp.json()
    assert data["status"] == "invalid"
    assert "error" in data


def test_consulta_single_exception_returns_500(client, monkeypatch):
    def fake_run_single(consulta_param, refine_param):
        raise RuntimeError("falha interna")

    monkeypatch.setattr("api.views._run_single", fake_run_single)
    resp = client.post("/api/consulta/", data={"consulta": "FULANO TESTE", "refine": False}, format="json")
    assert resp.status_code == 500
    data = resp.json()
    assert data["status"] == "error"
    assert "falha interna" in data["error"]


def test_consulta_single_refine_true_is_forwarded(client, monkeypatch):
    calls = []

    def fake_run_single(consulta_param, refine_param):
        calls.append({"consulta": consulta_param, "refine": refine_param})
        return {"status": "ok", "pessoa": {"nome": "Teste"}, "beneficios": []}

    monkeypatch.setattr("api.views._run_single", fake_run_single)
    resp = client.post("/api/consulta/", data={"consulta": "FULANO TESTE", "refine": True}, format="json")
    assert resp.status_code == 200
    assert len(calls) == 1
    assert calls[0]["refine"] is True


def test_consulta_itens_refine_default_false_and_true_override(client, monkeypatch):
    calls = []

    def fake_run_single(consulta_param, refine_param):
        calls.append({"consulta": consulta_param, "refine": refine_param})
        return {"status": "ok", "pessoa": {"nome": consulta_param}, "beneficios": []}

    monkeypatch.setattr("api.views._run_single", fake_run_single)
    payload = {
        "itens": [
            {"consulta": "A LIDA PEREIRA FIALHO"},
            {"consulta": "A ANNE CHRISTINE SILVA RIBEIRO", "refine": True},
        ]
    }
    resp = client.post("/api/consulta/", data=payload, format="json")
    assert resp.status_code == 200
    assert len(calls) == 2
    assert calls[0]["refine"] is False
    assert calls[1]["refine"] is True
