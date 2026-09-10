"""BaseSpider — abstract foundation for all source-specific spiders."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

from bs4 import BeautifulSoup
from loguru import logger
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from scraper.config.settings import Settings, get_settings
from scraper.config.sources import Source
from scraper.pipelines.html_cleaner import normalize_url
from scraper.pipelines.http_client import HttpClient

T = TypeVar("T")


class ScraperError(Exception):
    """Non-recoverable error during scraping."""

    pass


class BaseSpider(ABC, Generic[T]):
    """Abstract base class for all scraping spiders.

    Subclasses must implement ``parse_list_page`` and ``parse_detail_page``.
    """

    def __init__(self, source: Source, settings: Settings | None = None) -> None:
        self.source = source
        self.settings = settings or get_settings()
        self.http: HttpClient | None = None
        self._seen_urls: set[str] = set()
        self._stats = {"pages_visited": 0, "items_found": 0, "errors": 0}

    @property
    def key(self) -> str:
        return self.source.key

    @property
    def data_dir(self) -> Path:
        d = self.settings.data_dir / "raw" / self.key
        d.mkdir(parents=True, exist_ok=True)
        return d

    # --- Abstract methods ---

    @abstractmethod
    async def parse_list_page(self, html: str, url: str) -> list[T]:
        """Parse a listing page and return extracted items."""
        raise NotImplementedError

    @abstractmethod
    async def parse_detail_page(self, html: str, url: str) -> dict | None:
        """Parse a detail page and return structured data dict."""
        raise NotImplementedError

    # --- Hooks (override for custom behaviour) ---

    async def parse_startup_card(self, card_html: str, card_url: str) -> dict | None:
        """Override to parse a startup card from a list. Default calls parse_detail_page."""
        return await self.parse_detail_page(card_html, card_url)

    async def on_start(self) -> None:
        """Called once before scraping begins. Override for setup."""
        logger.info(f"[{self.key}] Starting spider")

    async def on_end(self) -> None:
        """Called once after scraping finishes. Override for teardown."""
        logger.info(f"[{self.key}] Finished — {self._stats}")

    # --- Public API ---

    async def run(self, http: HttpClient) -> list[T]:
        """Run the spider against all seed URLs and return collected items."""
        self.http = http
        await self.on_start()

        all_items: list[T] = []
        for seed_url in self.source.seed_urls:
            logger.info(f"[{self.key}] Fetching seed: {seed_url}")
            try:
                items = await self._scrape_seed(seed_url)
                all_items.extend(items)
            except Exception as e:
                logger.error(f"[{self.key}] Failed seed {seed_url}: {e}")
                self._stats["errors"] += 1

        await self.on_end()
        return all_items

    async def _scrape_seed(self, seed_url: str) -> list[T]:
        html = await self._fetch(seed_url)
        if not html:
            return []
        self._stats["pages_visited"] += 1
        return await self.parse_list_page(html, seed_url)

    async def _fetch(self, url: str) -> str | None:
        if self.source.requires_javascript:
            html = await self._fetch_with_playwright(url)
        else:
            text = await self.http.get_text(url)
            html = text
        if html:
            self._save_raw(url, html)
        return html

    async def _fetch_with_playwright(self, url: str) -> str | None:
        """Fetch a page rendered with JavaScript using Playwright."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(f"[{self.key}] Playwright not installed, cannot fetch JS page: {url}")
            return None

        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self.settings.scraper_user_agent,
                )
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=self.settings.scraper_timeout * 1000)
                # Wait for initial render
                await page.wait_for_timeout(3000)
                # Scroll to bottom to trigger lazy loading
                for _ in range(5):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await page.wait_for_timeout(1500)
                # Scroll back to top
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(1000)
                html = await page.content()
                await browser.close()
                logger.debug(f"[{self.key}] Playwright fetched: {url} ({len(html)} bytes)")
                return html
            except Exception as e:
                logger.error(f"[{self.key}] Playwright failed for {url}: {e}")
                return None

    async def fetch_detail(self, url: str) -> str | None:
        """Fetch and cache a detail page. Idempotent."""
        cached = self.data_dir / f"{self._url_filename(url)}.html"
        if cached.exists():
            logger.debug(f"[{self.key}] Using cached: {url}")
            return cached.read_text(encoding="utf-8")
        return await self._fetch(url)

    def _save_raw(self, url: str, html: str) -> None:
        path = self.data_dir / f"{self._url_filename(url)}.html"
        path.write_text(html, encoding="utf-8")

    def _url_filename(self, url: str) -> str:
        import hashlib
        key = hashlib.sha256(url.encode()).hexdigest()[:16]
        return f"page_{key}"

    def mark_seen(self, url: str) -> bool:
        """Return True if URL is new (not yet seen)."""
        normalized = url.lower().strip()
        if normalized in self._seen_urls:
            return False
        self._seen_urls.add(normalized)
        return True

    async def _retry_fetch(self, url: str, max_attempts: int = 3) -> str | None:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=2, max=15),
            retry=retry_if_exception_type((Exception,)),
            reraise=True,
        ):
            with attempt:
                text = await self.fetch_detail(url)
                if text is None:
                    raise ScraperError(f"Failed to fetch {url}")
                return text

    # --- Helpers ---

    def extract_links(self, html: str, base_url: str, selector: str = "a[href]") -> list[str]:
        """Extract all links matching a CSS selector, resolved to absolute URLs."""
        soup = BeautifulSoup(html, "lxml")
        links: list[str] = []
        for tag in soup.select(selector):
            href = tag.get("href")
            if href:
                resolved = normalize_url(base_url, href)
                if resolved:
                    links.append(resolved)
        return links

    def extract_links_unique(self, html: str, base_url: str, selector: str = "a[href]") -> list[str]:
        """Like extract_links but deduplicated and respecting seen URLs."""
        all_links = self.extract_links(html, base_url, selector)
        return [u for u in all_links if self.mark_seen(u)]

    def save_item(self, item: dict, filename: str | None = None) -> Path:
        """Save a scraped item as JSON to the raw data dir."""
        import uuid
        filename = filename or f"item_{uuid.uuid4().hex[:12]}.json"
        path = self.data_dir / filename
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @property
    def stats(self) -> dict:
        return self._stats.copy()
