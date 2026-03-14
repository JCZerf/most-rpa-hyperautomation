import os
from typing import Any, Tuple
from playwright.sync_api import Playwright


def create_browser_context(pw: Playwright, headless: bool, user_agent: str, viewport: dict, locale: str, timezone_id: str) -> Tuple[Any, Any, Any]:
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO_MS", "0"))

    browser = pw.chromium.launch(
        headless=headless,
        slow_mo=slow_mo,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )

    context = browser.new_context(
        user_agent=user_agent,
        viewport=viewport,
        locale=locale,
        timezone_id=timezone_id,
    )
    page = context.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return browser, context, page
