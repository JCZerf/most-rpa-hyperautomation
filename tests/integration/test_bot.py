import asyncio

from bot.engine.scraper import TransparencyBotAsync


class DummyContext:
    pass


class DummyPage:
    pass


def _run_bot_with_mocks(bot: TransparencyBotAsync) -> dict:
    return asyncio.run(bot.run_with_page_async(DummyContext(), DummyPage()))


def test_bot_zero_result(monkeypatch):
    async def fake_search(page, url_base, alvo, usar_refine):
        return {
            "zero": True,
            "evidencia_base64": "abc",
            "data_consulta": "01/01/2026",
            "hora_consulta": "12:00",
            "mensagem": "Não foi possível retornar os dados no tempo de resposta solicitado",
        }

    monkeypatch.setattr("bot.engine.scraper.perform_search_async", fake_search)
    bot = TransparencyBotAsync(headless=True, alvo="FULANO TESTE")
    result = _run_bot_with_mocks(bot)

    assert result["status"] == "not_found"
    assert result["meta"]["resultados_encontrados"] == 0
    assert result["pessoa"]["consulta"] == "FULANO TESTE"
    assert result["pessoa"]["nome"] == "N/A"
    assert result["pessoa"]["cpf"] == "N/A"
    assert result["pessoa"]["localidade"] == "N/A"
    assert result["beneficios"] == []
    assert result["id_consulta"]
    assert result["data_hora_consulta"]
    assert result["meta"]["id_consulta"] == result["id_consulta"]
    assert result["meta"]["data_hora_consulta"] == result["data_hora_consulta"]


def test_bot_sem_beneficio(monkeypatch):
    async def fake_search(page, url_base, alvo, usar_refine):
        return {"zero": False, "quantidade": 1}

    async def fake_pessoal(page):
        return {"nome": "Fulano", "cpf": "52998224725", "localidade": "SP"}

    async def fake_preparar(self, page):
        return None

    async def fake_benefits(context, page, url_base):
        return {
            "beneficios_encontrados": [],
            "panorama_base64": "pan",
            "total_valor_recebido": 0.0,
            "total_valor_recebido_formatado": "R$ 0,00",
            "data_consulta": "01/01/2026",
            "hora_consulta": "12:00",
        }

    monkeypatch.setattr("bot.engine.scraper.perform_search_async", fake_search)
    monkeypatch.setattr("bot.engine.scraper.extract_personal_info_async", fake_pessoal)
    monkeypatch.setattr("bot.engine.scraper.extract_benefits_async", fake_benefits)
    monkeypatch.setattr(TransparencyBotAsync, "_preparar_detalhes_beneficio", fake_preparar)

    bot = TransparencyBotAsync(headless=True, alvo="FULANO TESTE")
    result = _run_bot_with_mocks(bot)

    assert result["beneficios"] == []
    assert result["pessoa"]["quantidade_beneficios"] == 0
    assert "evidencia_sem_beneficio" in result["meta"]
    assert result["meta"]["beneficios_encontrados"] == []
    assert result["meta"]["resultados_encontrados"] == 1
    assert result["meta"]["total_valor_recebido"] == 0.0
    assert result["meta"]["total_valor_recebido_formatado"] == "R$ 0,00"
    assert result["pessoa"]["total_recursos_favorecidos"] == "R$ 0,00"


def test_bot_com_beneficio(monkeypatch):
    async def fake_search(page, url_base, alvo, usar_refine):
        return {"zero": False, "quantidade": 2}

    async def fake_pessoal(page):
        return {"nome": "Fulano", "cpf": "52998224725", "localidade": "SP"}

    async def fake_preparar(self, page):
        return None

    async def fake_benefits(context, page, url_base):
        return {
            "beneficios_encontrados": ["Auxílio Brasil"],
            "beneficios_resultado": [{"tipo": "Auxílio Brasil", "nis": "123", "valor_recebido": "100"}],
            "quantidade_beneficios": 1,
            "panorama_base64": "pan",
            "total_valor_recebido": 100.0,
            "total_valor_recebido_formatado": "R$ 100,00",
            "data_consulta": "01/01/2026",
            "hora_consulta": "12:00",
        }

    monkeypatch.setattr("bot.engine.scraper.perform_search_async", fake_search)
    monkeypatch.setattr("bot.engine.scraper.extract_personal_info_async", fake_pessoal)
    monkeypatch.setattr("bot.engine.scraper.extract_benefits_async", fake_benefits)
    monkeypatch.setattr(TransparencyBotAsync, "_preparar_detalhes_beneficio", fake_preparar)

    bot = TransparencyBotAsync(headless=True, alvo="FULANO TESTE")
    result = _run_bot_with_mocks(bot)

    assert result["beneficios"][0]["tipo"] == "Auxílio Brasil"
    assert result["meta"]["beneficios_encontrados"] == ["Auxílio Brasil"]
    assert result["meta"]["resultados_encontrados"] == 2
    assert result["meta"]["total_valor_recebido"] == 100.0
    assert result["meta"]["total_valor_recebido_formatado"] == "R$ 100,00"
    assert result["pessoa"]["total_recursos_favorecidos"] == "R$ 100,00"
    assert result["id_consulta"]
    assert result["data_hora_consulta"]
    assert result["meta"]["id_consulta"] == result["id_consulta"]
    assert result["meta"]["data_hora_consulta"] == result["data_hora_consulta"]


def test_bot_nome_inexistente(monkeypatch):
    async def fake_search(page, url_base, alvo, usar_refine):
        return {
            "zero": True,
            "evidencia_base64": "abc",
            "data_consulta": "01/01/2026",
            "hora_consulta": "12:00",
            "mensagem": "Foram encontrados 0 resultados para o termo NOME INEXISTENTE",
        }

    monkeypatch.setattr("bot.engine.scraper.perform_search_async", fake_search)
    bot = TransparencyBotAsync(headless=True, alvo="NOME INEXISTENTE")
    result = _run_bot_with_mocks(bot)

    assert result["meta"]["resultados_encontrados"] == 0
    assert result["pessoa"]["consulta"] == "NOME INEXISTENTE"
    assert result["status"] == "not_found"
    assert "0 resultados" in result["meta"]["mensagem"]


def test_bot_detalhe_parcelas(monkeypatch):
    async def fake_search(page, url_base, alvo, usar_refine):
        return {"zero": False, "quantidade": 1}

    async def fake_pessoal(page):
        return {"nome": "Fulano", "cpf": "52998224725", "localidade": "SP"}

    async def fake_preparar(self, page):
        return None

    async def fake_benefits(context, page, url_base):
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

    monkeypatch.setattr("bot.engine.scraper.perform_search_async", fake_search)
    monkeypatch.setattr("bot.engine.scraper.extract_personal_info_async", fake_pessoal)
    monkeypatch.setattr("bot.engine.scraper.extract_benefits_async", fake_benefits)
    monkeypatch.setattr(TransparencyBotAsync, "_preparar_detalhes_beneficio", fake_preparar)

    bot = TransparencyBotAsync(headless=True, alvo="FULANO TESTE")
    result = _run_bot_with_mocks(bot)

    assert result["beneficios"][0]["parcelas"][0]["valor"] == "200"
    assert result["beneficios"][0]["detalhe_evidencia"] == "imgb64"


def test_bot_reporta_etapa_falha_no_meta(monkeypatch):
    async def fake_search(page, url_base, alvo, usar_refine):
        raise RuntimeError("[ETAPA:clicar_lupa_busca] Timeout ao clicar na lupa")

    monkeypatch.setattr("bot.engine.scraper.perform_search_async", fake_search)

    bot = TransparencyBotAsync(headless=True, alvo="FULANO TESTE")
    result = _run_bot_with_mocks(bot)

    assert result["status"] == "error"
    assert "clicar_lupa_busca" in result["error"]
    assert result["meta"]["etapa_falha"] == "clicar_lupa_busca"
