import os

from bot.browser import create_browser_context
from bot.scraper import TransparencyBot


class FakePage:
    def __init__(self):
        self.init_scripts = []

    def add_init_script(self, script):
        self.init_scripts.append(script)


class FakeContext:
    def __init__(self):
        self.new_page_calls = 0
        self.page = FakePage()

    def new_page(self):
        self.new_page_calls += 1
        return self.page

    def close(self):
        return None


class FakeBrowser:
    def __init__(self):
        self.new_context_kwargs = None
        self.context = FakeContext()

    def new_context(self, **kwargs):
        self.new_context_kwargs = kwargs
        return self.context

    def close(self):
        return None


class FakeChromium:
    def __init__(self):
        self.launch_kwargs = None
        self.browser = FakeBrowser()

    def launch(self, **kwargs):
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

    pw = FakePlaywright()
    browser, context, page = create_browser_context(
        pw,
        headless=True,
        user_agent="",
        viewport={"width": 1280, "height": 720},
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
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


def test_create_browser_context_respects_env_flags(monkeypatch, tmp_path):
    storage = tmp_path / "storage_state.json"
    storage.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("PLAYWRIGHT_CHANNEL", "chromium")
    monkeypatch.setenv("PLAYWRIGHT_USE_STEALTH_FLAGS", "true")
    monkeypatch.setenv("PLAYWRIGHT_HIDE_WEBDRIVER", "true")
    monkeypatch.setenv("PLAYWRIGHT_STORAGE_STATE_PATH", str(storage))
    monkeypatch.setenv("PLAYWRIGHT_SLOW_MO_MS", "25")

    pw = FakePlaywright()
    browser, context, page = create_browser_context(
        pw,
        headless=False,
        user_agent="UA-Teste",
        viewport={"width": 1200, "height": 700},
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
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


def test_create_browser_context_ignores_missing_storage_state(monkeypatch):
    monkeypatch.setenv("PLAYWRIGHT_STORAGE_STATE_PATH", "/tmp/arquivo-inexistente-state.json")
    monkeypatch.setenv("PLAYWRIGHT_USE_STEALTH_FLAGS", "false")
    monkeypatch.setenv("PLAYWRIGHT_HIDE_WEBDRIVER", "false")

    pw = FakePlaywright()
    browser, _, _ = create_browser_context(
        pw,
        headless=True,
        user_agent="",
        viewport={"width": 1000, "height": 700},
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
    )

    assert "storage_state" not in browser.new_context_kwargs


class DummyBrowser:
    def close(self):
        return None


class DummyContext:
    def close(self):
        return None


class DummyLocator:
    @property
    def first(self):
        return self

    def wait_for(self, *args, **kwargs):
        return None

    def click(self, *args, **kwargs):
        return None

    def scroll_into_view_if_needed(self):
        return None

    def dispatch_event(self, *args, **kwargs):
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


def test_scraper_passes_user_agent_from_env(monkeypatch):
    captured = {}

    def fake_create_browser_context(pw, **kwargs):
        captured.update(kwargs)
        return DummyBrowser(), DummyContext(), DummyPage()

    def fake_search(page, url_base, alvo, usar_refine):
        return {
            "zero": True,
            "evidencia_base64": "abc",
            "data_consulta": "01/01/2026",
            "hora_consulta": "12:00",
            "mensagem": "Foram encontrados 0 resultados",
        }

    monkeypatch.setenv("PLAYWRIGHT_USER_AGENT", "UA-via-env")
    monkeypatch.setattr("bot.scraper.sync_playwright", lambda: DummyPW())
    monkeypatch.setattr("bot.scraper.create_browser_context", fake_create_browser_context)
    monkeypatch.setattr("bot.scraper.perform_search", fake_search)

    bot = TransparencyBot(headless=True, alvo="FULANO TESTE")
    bot.run()

    assert captured["user_agent"] == "UA-via-env"
