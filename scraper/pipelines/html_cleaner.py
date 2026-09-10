"""HTML cleaning and text extraction utilities."""
from __future__ import annotations

import hashlib
import re
from datetime import date
from urllib.parse import urljoin, urlparse

import dateparser
import trafilatura
from bs4 import BeautifulSoup
from loguru import logger


def hash_url(url: str) -> str:
    """Stable hash for URL dedup."""
    return hashlib.sha256(url.strip().lower().encode("utf-8")).hexdigest()[:16]


def hash_text(text: str) -> str:
    """Stable hash for text dedup."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def normalize_url(base: str, href: str) -> str | None:
    """Resolve relative URLs and clean tracking params."""
    if not href:
        return None
    if href.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    absolute = urljoin(base, href)
    parsed = urlparse(absolute)
    if parsed.scheme not in ("http", "https"):
        return None
    return absolute


def clean_text(raw: str, *, max_length: int = 50_000) -> str:
    """Normalize whitespace and strip non-content chars."""
    if not raw:
        return ""
    text = re.sub(r"\s+", " ", raw).strip()
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    if len(text) > max_length:
        text = text[:max_length]
    return text


def extract_main_text(html: str, *, url: str | None = None) -> str:
    """Extract main article text from HTML using trafilatura + BS4 fallback."""
    if not html:
        return ""
    try:
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            favor_recall=True,
            url=url,
        )
        if extracted and len(extracted) > 80:
            return clean_text(extracted)
    except Exception as e:
        logger.debug(f"trafilatura failed: {e}")

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe", "form"]):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.find("body") or soup
    text = main.get_text(separator=" ", strip=True) if main else ""
    return clean_text(text)


def parse_date(date_str: str | None) -> date | None:
    """Best-effort date parser for pt-BR and en formats."""
    if not date_str:
        return None
    try:
        parsed = dateparser.parse(
            date_str,
            languages=["pt", "en"],
            settings={"PREFER_DATES_FROM": "past", "DATE_ORDER": "DMY"},
        )
        if parsed:
            return parsed.date()
    except Exception:
        return None
    return None


def find_jsonld(soup: BeautifulSoup) -> dict:
    """Extract first JSON-LD object as dict."""
    import json
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
            if isinstance(data, dict):
                return data
            if isinstance(data, list) and data:
                return data[0]
        except Exception:
            continue
    return {}


def extract_meta_description(soup: BeautifulSoup) -> str:
    """Try meta description, then og:description, then twitter:description."""
    for selector in [
        ("meta", {"name": "description"}),
        ("meta", {"property": "og:description"}),
        ("meta", {"name": "twitter:description"}),
    ]:
        tag = soup.find(selector[0], selector[1])
        if tag and tag.get("content"):
            return clean_text(tag["content"])
    return ""


def extract_title(soup: BeautifulSoup) -> str:
    for selector in [
        ("meta", {"property": "og:title"}),
        ("meta", {"name": "twitter:title"}),
    ]:
        tag = soup.find(selector[0], selector[1])
        if tag and tag.get("content"):
            return clean_text(tag["content"])
    if soup.title and soup.title.string:
        return clean_text(soup.title.string)
    h1 = soup.find("h1")
    if h1:
        return clean_text(h1.get_text())
    return ""
