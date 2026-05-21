"""
Shared utilities for all CFl_data scrapers.

Proxy:   DataImpulse residential — geo-targeted via DATAIMPULSE_USER env var.
         The workflow appends __cr.kw / __cr.sa / __cr.eg to the base username
         according to the daily rotation defined in PROXY_ROTATION_SETUP.md.

Env vars (set by GitHub Actions workflow):
    DATAIMPULSE_USER   full username including __cr.XX suffix  (e.g. abc123__cr.kw)
    DATAIMPULSE_PASS   proxy password
    DATAIMPULSE_HOST   proxy host   (default: gw.dataimpulse.com)
    DATAIMPULSE_PORT   proxy port   (default: 823)

Anti-detection delays (from PROXY_ROTATION_SETUP.md):
    Between pages         : random 1.5 – 3.5 s  (callers use random_delay())
    Between subcategories : random 3.0 – 7.0 s  (callers use random_delay(3.0, 7.0))
    Between detail pages  : 0.3 s minimum
"""

import os
import random
import time
import asyncio
import logging
from typing import Optional
from curl_cffi import requests as curl_requests

logger = logging.getLogger(__name__)


# ── User-agent / header pools ─────────────────────────────────────────────────

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
]

ACCEPT_LANGUAGES = [
    'en-US,en;q=0.9',
    'en-US,en;q=0.9,ar;q=0.8',
    'ar,en-US;q=0.9,en;q=0.8',
    'en-GB,en;q=0.9,ar;q=0.8',
    'en-US,en;q=0.8',
]


def get_random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def get_random_headers() -> dict:
    return {
        'User-Agent': get_random_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': random.choice(ACCEPT_LANGUAGES),
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }


def random_delay(min_seconds: float = 1.5, max_seconds: float = 3.5) -> None:
    """Synchronous random delay. Defaults tuned for anti-detection (1.5–3.5 s)."""
    time.sleep(random.uniform(min_seconds, max_seconds))


async def async_random_delay(min_seconds: float = 1.5, max_seconds: float = 3.5) -> None:
    """Asynchronous random delay. Defaults tuned for anti-detection (1.5–3.5 s)."""
    await asyncio.sleep(random.uniform(min_seconds, max_seconds))


def setup_session_with_random_headers(session) -> None:
    session.headers.update(get_random_headers())


def rotate_user_agent(session) -> None:
    """No-op for SmartSession — curl_cffi impersonation handles headers."""
    if isinstance(session, SmartSession):
        return
    if not isinstance(session, curl_requests.Session):
        session.headers['User-Agent'] = get_random_user_agent()


# ── DataImpulse proxy configuration ──────────────────────────────────────────

def _build_proxies() -> dict:
    """
    Build proxy dict from environment variables.
    DATAIMPULSE_USER must already include the __cr.XX geo suffix —
    the workflow appends it before running the scraper.
    Falls back to no proxy if env vars are not set (local dev without proxy).
    """
    user = os.environ.get("DATAIMPULSE_USER", "")
    password = os.environ.get("DATAIMPULSE_PASS", "")
    host = os.environ.get("DATAIMPULSE_HOST", "gw.dataimpulse.com")
    port = os.environ.get("DATAIMPULSE_PORT", "823")

    if not user or not password:
        logger.warning(
            "DATAIMPULSE_USER / DATAIMPULSE_PASS not set — running WITHOUT proxy. "
            "Set these env vars or the scraper will use your real IP."
        )
        return {}

    proxy_url = f"http://{user}:{password}@{host}:{port}"
    logger.info(f"Proxy: {host}:{port}  user={user}")
    return {"http": proxy_url, "https": proxy_url}


# Built once at import time — consistent for the lifetime of the process
PROXIES = _build_proxies()


def configure_session_proxy(session) -> None:
    """Configure a plain requests.Session to use DataImpulse proxy."""
    if PROXIES:
        session.proxies.update(PROXIES)


# ── TLS impersonation profiles ────────────────────────────────────────────────

_IMPERSONATION_PROFILES = [
    "chrome124",
    "chrome120",
    "chrome131",
    "safari18_0",
    "chrome116",
]


# ── SmartSession ──────────────────────────────────────────────────────────────

class _CachedResponse:
    """Zero-cost response object served from the in-memory URL cache."""

    status_code = 200

    def __init__(self, text: str):
        self.text = text
        self.content = text.encode("utf-8")

    def raise_for_status(self):
        pass


class SmartSession:
    """
    Drop-in replacement for requests.Session that:
    1. Routes all requests through DataImpulse residential proxy (geo from env var)
    2. Uses curl_cffi to impersonate a real browser TLS fingerprint
    3. Auto-retries with rotating impersonation profiles on 403
    4. Caches URL responses — duplicate fetches cost 0 extra requests
    5. Tracks request_count and cache_hits for reporting
    """

    def __init__(self):
        self._profile_index = 0
        self._session = curl_requests.Session(
            impersonate=_IMPERSONATION_PROFILES[0],
            proxies=PROXIES,
        )
        self._cache: dict = {}
        self.request_count = 0
        self.cache_hits = 0

    def _next_profile(self) -> str:
        self._profile_index = (self._profile_index + 1) % len(_IMPERSONATION_PROFILES)
        return _IMPERSONATION_PROFILES[self._profile_index]

    def get(self, url: str, **kwargs):
        # Serve from cache at zero cost
        if url in self._cache:
            self.cache_hits += 1
            logger.debug(f"Cache hit: {url}")
            return _CachedResponse(self._cache[url])

        last_exc = None
        for attempt in range(len(_IMPERSONATION_PROFILES)):
            try:
                if attempt > 0:
                    profile = self._next_profile()
                    logger.warning(
                        f"Retrying with profile '{profile}' "
                        f"(attempt {attempt + 1}/{len(_IMPERSONATION_PROFILES)})"
                    )
                    time.sleep(random.uniform(2.0, 4.0))
                    self._session = curl_requests.Session(
                        impersonate=profile,
                        proxies=PROXIES,
                    )

                response = self._session.get(url, **kwargs)

                if response.status_code == 403:
                    last_exc = Exception(f"HTTP 403 for {url}")
                    continue

                self.request_count += 1
                self._cache[url] = response.text
                return response

            except Exception as e:
                err_str = str(e)
                # Retry on 403 or connection-level failures (timeout, refused, reset)
                is_connection_error = any(
                    token in err_str
                    for token in ("403", "timed out", "timeout", "(28)", "(6)", "(7)", "(35)",
                                   "Connection", "CONNECT", "SSL", "RemoteDisconnected")
                )
                if is_connection_error:
                    last_exc = e
                    logger.warning(
                        f"Connection error on attempt {attempt + 1}: {err_str[:120]} — retrying"
                    )
                    continue
                raise

        raise last_exc or Exception(
            f"All {len(_IMPERSONATION_PROFILES)} retry attempts failed for {url}"
        )

    def close(self):
        if self._session:
            self._session.close()

    @property
    def headers(self):
        return self._session.headers

    @property
    def proxies(self):
        return self._session.proxies


def create_session() -> SmartSession:
    """
    Return a SmartSession backed by DataImpulse residential proxy.
    Geo is determined by DATAIMPULSE_USER env var (__cr.kw / __cr.sa / __cr.eg).
    """
    geo = ""
    user = os.environ.get("DATAIMPULSE_USER", "")
    if "__cr." in user:
        geo = user.split("__cr.")[-1]
    logger.info(
        f"SmartSession ready — DataImpulse proxy  geo={geo or 'not set'}  "
        f"host={os.environ.get('DATAIMPULSE_HOST', 'gw.dataimpulse.com')}"
    )
    return SmartSession()
