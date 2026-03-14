import pytest

from bot.scraper import TransparencyBot


class DummyBrowser:
    def close(self):
        return None


class DummyContext:
    def close(self):
        return None


class DummyLocator:
    def __init__(self):
        pass

    def first(self):
        return self

    @property
    def first(self):  # emulate playwright property
        return self

    def wait_for(self, *args, **kwargs):
        return None

    def click(self, *args, **kwargs):
        return None

    def scroll_into_view_if_needed(self):
        return None

    def dispatch_event(self, *args, **kwargs):
        return None

    def get_attribute(self, *args, **kwargs):
        return None


class DummyPage(DummyLocator):
    def get_by_role(self, *args, **kwargs):
        return DummyLocator()

    def locator(self, *args, **kwargs):
        return DummyLocator()


class DummyPW:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def dummy_browser_ctx(monkeypatch):
    def fake_create_browser_context(pw, **kwargs):
        return DummyBrowser(), DummyContext(), DummyPage()

    monkeypatch.setattr("bot.scraper.create_browser_context", fake_create_browser_context)
    monkeypatch.setattr("bot.scraper.sync_playwright", lambda: DummyPW())


def test_bot_zero_result(monkeypatch, dummy_browser_ctx):
    def fake_search(page, url_base, alvo, usar_refine):
        return {
            "zero": True,
            "evidencia_base64": "abc",
            "data_consulta": "01/01/2026",
            "hora_consulta": "12:00",
            "mensagem": "Não foi possível retornar os dados no tempo de resposta solicitado",
        }

    monkeypatch.setattr("bot.scraper.perform_search", fake_search)

    bot = TransparencyBot(headless=True, alvo="FULANO TESTE")
    result = bot.run()

    assert result["meta"]["resultados_encontrados"] == 0
    assert result["pessoa"]["consulta"] == "FULANO TESTE"
    assert result["status"] == "error"
    assert "Não foi possível retornar" in result["error"]
    assert result["beneficios"] == []


def test_bot_sem_beneficio(monkeypatch, dummy_browser_ctx):
    def fake_search(page, url_base, alvo, usar_refine):
        return {"zero": False, "quantidade": 1}

    def fake_pessoal(page):
        return {"nome": "Fulano", "cpf": "52998224725", "localidade": "SP"}

    def fake_benefits(context, page, url_base):
        return {
            "beneficios_encontrados": [],
            "panorama_base64": "pan",
            "data_consulta": "01/01/2026",
            "hora_consulta": "12:00",
        }

    monkeypatch.setattr("bot.scraper.perform_search", fake_search)
    monkeypatch.setattr("bot.scraper.extract_personal_info", fake_pessoal)
    monkeypatch.setattr("bot.scraper.extract_benefits", fake_benefits)

    bot = TransparencyBot(headless=True, alvo="FULANO TESTE")
    result = bot.run()

    assert result["beneficios"] == []
    assert result["pessoa"]["quantidade_beneficios"] == 0
    assert "evidencia_sem_beneficio" in result["meta"]
    assert result["meta"]["beneficios_encontrados"] == []
    assert result["meta"]["resultados_encontrados"] == 1


def test_bot_com_beneficio(monkeypatch, dummy_browser_ctx):
    def fake_search(page, url_base, alvo, usar_refine):
        return {"zero": False, "quantidade": 2}

    def fake_pessoal(page):
        return {"nome": "Fulano", "cpf": "52998224725", "localidade": "SP"}

    def fake_benefits(context, page, url_base):
        return {
            "beneficios_encontrados": ["Auxílio Brasil"],
            "beneficios_resultado": [{"tipo": "Auxílio Brasil", "nis": "123", "valor_recebido": "100"}],
            "quantidade_beneficios": 1,
            "panorama_base64": "pan",
            "data_consulta": "01/01/2026",
            "hora_consulta": "12:00",
        }

    monkeypatch.setattr("bot.scraper.perform_search", fake_search)
    monkeypatch.setattr("bot.scraper.extract_personal_info", fake_pessoal)
    monkeypatch.setattr("bot.scraper.extract_benefits", fake_benefits)

    bot = TransparencyBot(headless=True, alvo="FULANO TESTE")
    result = bot.run()

    assert result["beneficios"][0]["tipo"] == "Auxílio Brasil"
    assert result["meta"]["beneficios_encontrados"] == ["Auxílio Brasil"]
    assert result["meta"]["resultados_encontrados"] == 2


def test_bot_nome_inexistente(monkeypatch, dummy_browser_ctx):
    def fake_search(page, url_base, alvo, usar_refine):
        # simula busca sem resultados por nome
        return {
            "zero": True,
            "evidencia_base64": "abc",
            "data_consulta": "01/01/2026",
            "hora_consulta": "12:00",
            "mensagem": "Foram encontrados 0 resultados para o termo NOME INEXISTENTE",
        }

    monkeypatch.setattr("bot.scraper.perform_search", fake_search)

    bot = TransparencyBot(headless=True, alvo="NOME INEXISTENTE")
    result = bot.run()

    assert result["meta"]["resultados_encontrados"] == 0
    assert result["pessoa"]["consulta"] == "NOME INEXISTENTE"
    assert result["status"] == "error"
    assert "0 resultados" in result["error"] or "0 resultados" in result["meta"]["mensagem"]


def test_bot_detalhe_parcelas(monkeypatch, dummy_browser_ctx):
    def fake_search(page, url_base, alvo, usar_refine):
        return {"zero": False, "quantidade": 1}

    def fake_pessoal(page):
        return {"nome": "Fulano", "cpf": "52998224725", "localidade": "SP"}

    def fake_benefits(context, page, url_base):
        return {
            "beneficios_encontrados": ["Auxílio Emergencial"],
            "beneficios_resultado": [{
                "tipo": "Auxílio Emergencial",
                "nis": "123",
                "valor_recebido": "200",
                "detalhe_evidencia": "imgb64",
                "parcelas": [{"mes_folha": "01/2021", "valor": "200"}],
            }],
            "quantidade_beneficios": 1,
            "panorama_base64": "pan",
            "data_consulta": "01/01/2026",
            "hora_consulta": "12:00",
        }

    monkeypatch.setattr("bot.scraper.perform_search", fake_search)
    monkeypatch.setattr("bot.scraper.extract_personal_info", fake_pessoal)
    monkeypatch.setattr("bot.scraper.extract_benefits", fake_benefits)

    bot = TransparencyBot(headless=True, alvo="FULANO TESTE")
    result = bot.run()

    assert result["beneficios"][0]["parcelas"][0]["valor"] == "200"
    assert result["beneficios"][0]["detalhe_evidencia"] == "imgb64"
