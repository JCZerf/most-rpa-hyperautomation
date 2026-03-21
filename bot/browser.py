import os
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Tuple, Set
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


def _env_set_csv(name: str) -> Set[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return set()
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _is_same_or_subdomain(hostname: str, base_domain: str) -> bool:
    host = (hostname or "").lower()
    base = (base_domain or "").lower()
    return bool(host and base and (host == base or host.endswith(f".{base}")))

def create_browser_context(pw: Playwright, headless: bool, user_agent: str, viewport: dict, locale: str, timezone_id: str) -> Tuple[Any, Any, Any]:
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO_MS", "50"))
    channel = os.getenv("PLAYWRIGHT_CHANNEL", "chromium").strip() or "chromium"

    use_stealth_flags = _env_bool("PLAYWRIGHT_USE_STEALTH_FLAGS", True)
    use_stealth_package = _env_bool("PLAYWRIGHT_USE_STEALTH_PACKAGE", True) # Era False!
    hide_webdriver = _env_bool("PLAYWRIGHT_HIDE_WEBDRIVER", True)
    block_resource_types = _env_set_csv("PLAYWRIGHT_BLOCK_RESOURCE_TYPES")
    image_block_mode = os.getenv("PLAYWRIGHT_BLOCK_IMAGE_MODE", "third_party").strip().lower() or "third_party"
    primary_domain = os.getenv("PLAYWRIGHT_PRIMARY_DOMAIN", "portaldatransparencia.gov.br").strip().lower()
    image_allow_patterns = _env_set_csv("PLAYWRIGHT_IMAGE_ALLOW_PATTERNS")
    if not image_allow_patterns:
        image_allow_patterns = {"captcha", "challenge", "recaptcha", "hcaptcha", "cloudflare", "human"}
    storage_state_path = os.getenv("PLAYWRIGHT_STORAGE_STATE_PATH", "").strip()

    launch_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ]
    if use_stealth_flags:
        launch_args.extend([
            "--disable-blink-features",
            "--disable-blink-features=AutomationControlled",
        ])

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
        "device_scale_factor": 1, 
    }

    if user_agent:
        context_kwargs["user_agent"] = user_agent

    if storage_state_path and Path(storage_state_path).is_file():
        context_kwargs["storage_state"] = storage_state_path

    context = browser.new_context(**context_kwargs)

    if block_resource_types:
        def _route_handler(route, request):
            resource_type = (request.resource_type or "").lower()
            if resource_type not in block_resource_types:
                route.continue_()
                return

            if resource_type == "image":
                request_url = request.url or ""
                request_host = urlparse(request_url).hostname or ""
                if any(pattern in request_url.lower() for pattern in image_allow_patterns):
                    route.continue_()
                    return
                if image_block_mode == "off":
                    route.continue_()
                    return
                if image_block_mode == "third_party" and _is_same_or_subdomain(request_host, primary_domain):
                    route.continue_()
                    return

            route.abort()
        context.route("**/*", _route_handler)

    page = context.new_page()

    if stealth_sync is not None and use_stealth_package:
        stealth_sync(page)

    if hide_webdriver:
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return browser, context, page
