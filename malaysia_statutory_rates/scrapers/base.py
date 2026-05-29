"""Base scraper with httpx + Firecrawl fallback, change detection, JSON saving."""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent.parent / ".env")


class BaseScraper:
    """Base class for all statutory rate scrapers.

    Fetching strategy:
    1. Try httpx with browser-like headers
    2. On 403/429, fall back to Firecrawl (if FIRECRAWL_API_KEY set)
    """

    SOURCE_URL: str = ""
    SOURCE_NAME: str = ""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path(__file__).parent.parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-MY,en;q=0.9,en-US;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        )

    def _get_firecrawl_key(self) -> str | None:
        """Get Firecrawl API key from .env."""
        return os.environ.get("FIRECRAWL_API_KEY")

    def _fetch_firecrawl(self, url: str) -> str:
        """Fetch via Firecrawl CLI (firecrawl_scrape MCP tool wrapper)."""
        key = self._get_firecrawl_key()
        if not key:
            raise RuntimeError(
                f"Cannot fetch {url}: httpx blocked and no Firecrawl API key available. "
                "Set FIRECRAWL_API_KEY env var or store in macOS Keychain."
            )
        # Use firecrawl-py SDK
        from firecrawl import FirecrawlApp

        app = FirecrawlApp(api_key=key)
        result = app.scrape_url(url, formats=["markdown", "html"])
        if not result or (not result.html and not result.markdown):
            raise RuntimeError(f"Firecrawl returned empty for {url}")
        return result.html or result.markdown

    def fetch(self, url: str, retries: int = 3) -> str:
        """Fetch URL with httpx first, Firecrawl fallback on 403/429."""
        # Try httpx first
        for attempt in range(retries):
            try:
                resp = self.client.get(url)
                resp.raise_for_status()
                return resp.text
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (403, 429):
                    print(f"    {url}: {e.response.status_code}, falling back to Firecrawl...")
                    return self._fetch_firecrawl(url)
                if attempt == retries - 1:
                    raise
                wait = 2**attempt
                print(f"    Retry {attempt + 1}/{retries} ({e}), waiting {wait}s...")
                time.sleep(wait)
            except httpx.HTTPError as e:
                if attempt == retries - 1:
                    # Last attempt failed, try Firecrawl
                    print(f"    httpx failed ({e}), trying Firecrawl...")
                    return self._fetch_firecrawl(url)
                wait = 2**attempt
                print(f"    Retry {attempt + 1}/{retries} ({e}), waiting {wait}s...")
                time.sleep(wait)
        raise RuntimeError(f"Failed to fetch {url}")

    def scrape(self) -> dict | None:
        """Scrape data. Return dict if changed, None if unchanged.

        Subclasses MUST implement this.
        """
        raise NotImplementedError

    def save(self, filename: str, data: dict) -> Path:
        """Save data to JSON with metadata."""
        data["_metadata"] = {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "source": self.SOURCE_URL,
            "source_name": self.SOURCE_NAME,
            "scraper_version": "0.1.0",
        }
        path = self.data_dir / filename
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def has_changed(self, filename: str, new_data: dict) -> bool:
        """Check if data changed since last scrape."""
        path = self.data_dir / filename
        if not path.exists():
            return True
        old = json.loads(path.read_text(encoding="utf-8"))
        old.pop("_metadata", None)
        new_copy = {k: v for k, v in new_data.items() if k != "_metadata"}
        return old != new_copy

    def close(self) -> None:
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
