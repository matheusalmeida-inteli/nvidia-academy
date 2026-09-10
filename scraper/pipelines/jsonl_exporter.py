"""JSONL exporter — writes scraped data to newline-delimited JSON for offline use.

This is the primary output mode when no Postgres is available.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, datetime

from loguru import logger

from scraper.config.settings import Settings, get_settings


def _serialize(obj):
    """JSON serializer for dates and datetimes."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, set):
        return sorted(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


class JSONLExporter:
    """Write startup/doc records to JSONL files."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.exports_dir = self.settings.exports_dir
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.startups_path = self.exports_dir / "startups.jsonl"
        self.docs_path = self.exports_dir / "documentos.jsonl"
        self.articles_path = self.exports_dir / "articles.jsonl"

    def write_startups(self, startups: Iterable[dict], *, append: bool = False) -> int:
        mode = "a" if append else "w"
        count = 0
        seen: set[str] = set()

        if append and self.startups_path.exists():
            with self.startups_path.open() as f:
                for line in f:
                    try:
                        existing = json.loads(line)
                        key = (existing.get("nome", "").lower(), existing.get("site", "").lower())
                        seen.add(f"{key[0]}|{key[1]}")
                    except Exception:
                        pass

        with self.startups_path.open(mode, encoding="utf-8") as f:
            for s in startups:
                nome = (s.get("nome") or "").strip()
                site = (s.get("site") or "").strip().lower()
                if not nome:
                    continue
                key = f"{nome.lower()}|{site}"
                if key in seen:
                    continue
                seen.add(key)
                f.write(json.dumps(s, ensure_ascii=False, default=_serialize) + "\n")
                count += 1
        logger.info(f"Exported {count} startups to {self.startups_path}")
        return count

    def write_articles(self, articles: Iterable[dict], *, append: bool = False) -> int:
        """Write article-level data from news spiders."""
        mode = "a" if append else "w"
        count = 0
        seen: set[str] = set()
        if append and self.articles_path.exists():
            with self.articles_path.open() as f:
                for line in f:
                    try:
                        existing = json.loads(line)
                        seen.add(existing.get("url", ""))
                    except Exception:
                        pass

        with self.articles_path.open(mode, encoding="utf-8") as f:
            for a in articles:
                url = (a.get("url") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                f.write(json.dumps(a, ensure_ascii=False, default=_serialize) + "\n")
                count += 1
        logger.info(f"Exported {count} articles to {self.articles_path}")
        return count

    def write_documents(self, docs: Iterable[dict], *, append: bool = False) -> int:
        mode = "a" if append else "w"
        count = 0
        with self.docs_path.open(mode, encoding="utf-8") as f:
            for d in docs:
                if not d.get("conteudo_texto") or not d.get("url_fonte"):
                    continue
                f.write(json.dumps(d, ensure_ascii=False, default=_serialize) + "\n")
                count += 1
        logger.info(f"Exported {count} documents to {self.docs_path}")
        return count

    def load_startups(self) -> list[dict]:
        if not self.startups_path.exists():
            return []
        result = []
        with self.startups_path.open() as f:
            for line in f:
                try:
                    result.append(json.loads(line))
                except Exception:
                    pass
        return result

    def load_articles(self) -> list[dict]:
        if not self.articles_path.exists():
            return []
        result = []
        with self.articles_path.open() as f:
            for line in f:
                try:
                    result.append(json.loads(line))
                except Exception:
                    pass
        return result

    def stats(self) -> dict:
        startups = self.load_startups()
        articles = self.load_articles()
        docs_count = sum(1 for _ in self.docs_path.open()) if self.docs_path.exists() else 0
        return {
            "startups_file": str(self.startups_path),
            "startups_count": len(startups),
            "articles_file": str(self.articles_path),
            "articles_count": len(articles),
            "docs_file": str(self.docs_path),
            "docs_count": docs_count,
        }
