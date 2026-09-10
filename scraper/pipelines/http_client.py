"""HTTP client with rate limiting, retries, and robots.txt respect."""
from __future__ import annotations

import asyncio
import random
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from loguru import logger
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from scraper.config.settings import Settings, get_settings


class HttpClient:
    """Async HTTP client with per-domain throttling and robots.txt support."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._domain_locks: dict[str, asyncio.Lock] = {}
        self._last_request_at: dict[str, float] = {}
        self._robots_cache: dict[str, RobotFileParser | None] = {}
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> HttpClient:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.settings.scraper_timeout),
            headers={
                "User-Agent": self.settings.scraper_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Cache-Control": "no-cache",
            },
            follow_redirects=True,
            http2=False,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("HttpClient must be used as async context manager")
        return self._client

    def _get_domain(self, url: str) -> str:
        return urlparse(url).netloc

    def _get_lock(self, domain: str) -> asyncio.Lock:
        if domain not in self._domain_locks:
            self._domain_locks[domain] = asyncio.Lock()
        return self._domain_locks[domain]

    async def _throttle(self, url: str) -> None:
        domain = self._get_domain(url)
        async with self._get_lock(domain):
            now = asyncio.get_event_loop().time()
            last = self._last_request_at.get(domain, 0.0)
            delay = random.uniform(self.settings.scraper_min_delay, self.settings.scraper_max_delay)
            wait = (last + delay) - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at[domain] = asyncio.get_event_loop().time()

    def _get_robots_parser(self, url: str) -> RobotFileParser | None:
        if not self.settings.scraper_respect_robots:
            return None
        domain = self._get_domain(url)
        if domain in self._robots_cache:
            return self._robots_cache[domain]
        robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
        try:
            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.read()
            self._robots_cache[domain] = parser
            return parser
        except Exception as e:
            logger.warning(f"Failed to read robots.txt at {robots_url}: {e}")
            self._robots_cache[domain] = None
            return None

    def is_allowed(self, url: str) -> bool:
        parser = self._get_robots_parser(url)
        if parser is None:
            return True
        try:
            return parser.can_fetch(self.settings.scraper_user_agent, url)
        except Exception:
            return True

    async def get(self, url: str, *, allow_disallowed: bool = False) -> httpx.Response | None:
        if not allow_disallowed and not self.is_allowed(url):
            logger.warning(f"Disallowed by robots.txt: {url}")
            return None

        await self._throttle(url)

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)),
            reraise=True,
        ):
            with attempt:
                try:
                    response = await self.client.get(url)
                    response.raise_for_status()
                    logger.debug(f"GET {url} -> {response.status_code} ({len(response.content)} bytes)")
                    return response
                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    if status in (403, 404, 410):
                        logger.warning(f"GET {url} -> {status} (not retried)")
                        return None
                    raise
                except (httpx.TimeoutException, httpx.NetworkError) as e:
                    logger.warning(f"GET {url} -> {type(e).__name__} (retry)")
                    raise
        return None

    async def get_text(self, url: str) -> str | None:
        response = await self.get(url)
        if response is None:
            return None
        return response.text

    async def get_bytes(self, url: str) -> bytes | None:
        response = await self.get(url)
        if response is None:
            return None
        return response.content
