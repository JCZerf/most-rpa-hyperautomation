import asyncio

from bot.engine.browser import create_browser_context_async
from bot.engine.scraper import TransparencyBotAsync


class FakePage:
    def __init__(self):
        self.init_scripts = []

    async def add_init_script(self, script):
        self.init_scripts.append(script)


class FakeContext:
    def __init__(self):
        self.new_page_calls = 0
        self.page = FakePage()
        self.route_calls = []

    async def new_page(self):
        self.new_page_calls += 1
        return self.page

    async def route(self, pattern, handler):
        self.route_calls.append((pattern, handler))

    async def close(self):
        return None


class FakeBrowser:
    def __init__(self):
        self.new_context_kwargs = None
        self.context = FakeContext()

    async def new_context(self, **kwargs):
        self.new_context_kwargs = kwargs
        return self.context

    async def close(self):
        return None


class FakeChromium:
    def __init__(self):
        self.launch_kwargs = None
        self.browser = FakeBrowser()

    async def launch(self, **kwargs):
        self.launch_kwargs = kwargs
        return self.browser


class FakePlaywright:
    def __init__(self):
        self.chromium = FakeChromium()


def test_create_browser_context_defaults(monkeypatch):
    monkeypatch.delenv("PLAYWRIGHT_CHANNEL", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_USE_STEALTH_FLAGS", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_HIDE_WEBDRIVER", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_STORAGE_STATE_PATH", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_SLOW_MO_MS", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_BLOCK_RESOURCE_TYPES", raising=False)

    pw = FakePlaywright()
    browser, context, page = asyncio.run(
        create_browser_context_async(
            pw,
            headless=True,
            user_agent="",
            viewport={"width": 1280, "height": 720},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )
    )

    assert browser is pw.chromium.browser
    assert context is browser.context
    assert page is context.page
    assert pw.chromium.launch_kwargs["channel"] == "chromium"
    assert "--disable-blink-features=AutomationControlled" in pw.chromium.launch_kwargs["args"]
    assert browser.new_context_kwargs["viewport"] == {"width": 1280, "height": 720}
    assert browser.new_context_kwargs["locale"] == "pt-BR"
    assert browser.new_context_kwargs["timezone_id"] == "America/Sao_Paulo"
    assert "user_agent" not in browser.new_context_kwargs
    assert "storage_state" not in browser.new_context_kwargs
    assert len(context.page.init_scripts) == 1
    assert len(context.route_calls) == 0


def test_create_browser_context_respects_env_flags(monkeypatch, tmp_path):
    storage = tmp_path / "storage_state.json"
    storage.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("PLAYWRIGHT_CHANNEL", "chromium")
    monkeypatch.setenv("PLAYWRIGHT_USE_STEALTH_FLAGS", "true")
    monkeypatch.setenv("PLAYWRIGHT_HIDE_WEBDRIVER", "true")
    monkeypatch.setenv("PLAYWRIGHT_STORAGE_STATE_PATH", str(storage))
    monkeypatch.setenv("PLAYWRIGHT_SLOW_MO_MS", "25")
    monkeypatch.setenv("PLAYWRIGHT_BLOCK_RESOURCE_TYPES", "font,media")

    pw = FakePlaywright()
    browser, context, page = asyncio.run(
        create_browser_context_async(
            pw,
            headless=False,
            user_agent="UA-Teste",
            viewport={"width": 1200, "height": 700},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )
    )

    assert browser is pw.chromium.browser
    assert context is browser.context
    assert page is context.page
    assert pw.chromium.launch_kwargs["channel"] == "chromium"
    assert pw.chromium.launch_kwargs["slow_mo"] == 25
    assert "--disable-blink-features=AutomationControlled" in pw.chromium.launch_kwargs["args"]
    assert browser.new_context_kwargs["user_agent"] == "UA-Teste"
    assert browser.new_context_kwargs["storage_state"] == str(storage)
    assert len(context.page.init_scripts) == 1
    assert len(context.route_calls) == 1
    assert context.route_calls[0][0] == "**/*"


def test_create_browser_context_ignores_missing_storage_state(monkeypatch):
    monkeypatch.setenv("PLAYWRIGHT_STORAGE_STATE_PATH", "/tmp/arquivo-inexistente-state.json")
    monkeypatch.setenv("PLAYWRIGHT_USE_STEALTH_FLAGS", "false")
    monkeypatch.setenv("PLAYWRIGHT_HIDE_WEBDRIVER", "false")

    pw = FakePlaywright()
    browser, _, _ = asyncio.run(
        create_browser_context_async(
            pw,
            headless=True,
            user_agent="",
            viewport={"width": 1000, "height": 700},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )
    )

    assert "storage_state" not in browser.new_context_kwargs
    assert "--disable-blink-features=AutomationControlled" not in pw.chromium.launch_kwargs["args"]
    assert len(pw.chromium.browser.context.page.init_scripts) == 0


class DummyBrowser:
    async def close(self):
        return None


class DummyContext:
    async def close(self):
        return None


class DummyPage:
    pass


class DummyAsyncPW:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_scraper_usa_user_agent_do_perfil(monkeypatch):
    captured = {}

    async def fake_create_browser_context_async(pw, **kwargs):
        captured.update(kwargs)
        return DummyBrowser(), DummyContext(), DummyPage()

    async def fake_fluxo_auditado(self, context, page, *, id_consulta, data_hora_consulta):
        return {
            "status": "not_found",
            "id_consulta": id_consulta,
            "data_hora_consulta": data_hora_consulta,
            "pessoa": {"consulta": self.alvo, "nome": "N/A", "cpf": "N/A", "localidade": "N/A"},
            "beneficios": [],
            "meta": {"id_consulta": id_consulta, "data_hora_consulta": data_hora_consulta, "resultados_encontrados": 0},
        }

    monkeypatch.setattr("bot.engine.scraper.async_playwright", lambda: DummyAsyncPW())
    monkeypatch.setattr("bot.engine.scraper.create_browser_context_async", fake_create_browser_context_async)
    monkeypatch.setattr(
        "bot.engine.scraper.get_random_profile",
        lambda: {
            "name": "perfil-teste",
            "user_agent": "UA-via-profile",
            "viewport": {"width": 1366, "height": 768},
            "locale": "pt-BR",
            "timezone_id": "America/Sao_Paulo",
        },
    )
    monkeypatch.setattr(TransparencyBotAsync, "_executar_fluxo_com_auditoria", fake_fluxo_auditado)

    bot = TransparencyBotAsync(headless=True, alvo="FULANO TESTE")
    result = asyncio.run(bot.run_async())

    assert captured["user_agent"] == "UA-via-profile"
    assert captured["viewport"] == {"width": 1366, "height": 768}
    assert result["status"] == "not_found"
