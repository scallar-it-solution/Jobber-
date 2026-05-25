from __future__ import annotations

import os
import random
import time


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def random_delay(min_seconds: float = 2.0, max_seconds: float = 5.0) -> None:
    time.sleep(random.uniform(min_seconds, max_seconds))


def proxy_for_requests() -> dict[str, str] | None:
    proxies = [proxy.strip() for proxy in os.getenv("PROXY_LIST", "").split(",") if proxy.strip()]
    if not proxies:
        return None
    proxy = random.choice(proxies)
    return {"http": proxy, "https": proxy}


def proxy_for_playwright() -> dict[str, str] | None:
    proxies = [proxy.strip() for proxy in os.getenv("PROXY_LIST", "").split(",") if proxy.strip()]
    if not proxies:
        return None
    return {"server": random.choice(proxies)}

