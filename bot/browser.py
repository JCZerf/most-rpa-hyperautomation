import os
from pathlib import Path
from typing import Any, Tuple
from playwright.sync_api import Playwright


try:
    from playwright_stealth import stealth_sync
except ImportError:
    stealth_sync = None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def create_browser_context(pw: Playwright, headless: bool, user_agent: str, viewport: dict, locale: str, timezone_id: str) -> Tuple[Any, Any, Any]:
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO_MS", "50"))
    channel = os.getenv("PLAYWRIGHT_CHANNEL", "chromium").strip() or "chromium"

    # Flags de inicialização
    use_stealth_flags = _env_bool("PLAYWRIGHT_USE_STEALTH_FLAGS", True)
    use_stealth_package = _env_bool("PLAYWRIGHT_USE_STEALTH_PACKAGE", True)
    hide_webdriver = _env_bool("PLAYWRIGHT_HIDE_WEBDRIVER", True)
    storage_state_path = os.getenv("PLAYWRIGHT_STORAGE_STATE_PATH", "").strip()

    launch_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ]
    if use_stealth_flags:
        launch_args.append("--disable-blink-features=AutomationControlled")

    browser = pw.chromium.launch(
        headless=headless,
        slow_mo=slow_mo,
        channel=channel,
        args=launch_args,
    )

    context_kwargs = {
        "viewport": viewport,
        "locale": locale,
        "timezone_id": timezone_id,
    }

    if user_agent:
        context_kwargs["user_agent"] = user_agent

    if storage_state_path and Path(storage_state_path).is_file():
        context_kwargs["storage_state"] = storage_state_path

    context = browser.new_context(**context_kwargs)
    page = context.new_page()

    if use_stealth_package and stealth_sync is not None:
        stealth_sync(page)
    elif hide_webdriver:
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return browser, context, page
