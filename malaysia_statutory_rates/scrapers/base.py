"""Base scraper with httpx + Firecrawl fallback, robots.txt compliance, change detection."""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Cache robots.txt parsers per domain
_robots_cache: dict[str, RobotFileParser] = {}


def _get_robots(url: str) -> RobotFileParser:
    """Fetch and cache robots.txt for a URL's domain."""
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in _robots_cache:
        rp = RobotFileParser()
        robots_url = f"{origin}/robots.txt"
        try:
            rp.set_url(robots_url)
            rp.read()
        except Exception:
            # If robots.txt unavailable, allow everything
            rp.allow_all = True
        _robots_cache[origin] = rp
    return _robots_cache[origin]


USER_AGENT = "malaysia-statutory-rates/0.1 (+https://github.com/faizalmy/malaysia-statutory-rates)"


class BaseScraper:
    """Base class for all statutory rate scrapers.

    Fetching strategy:
    1. Check robots.txt — skip if disallowed
    2. Try httpx with browser-like headers
    3. On 403/429, fall back to Firecrawl (if FIRECRAWL_API_KEY set)
    """

    SOURCE_URL: str = ""
    SOURCE_NAME: str = ""

    def __init__(self, data_dir: Path | None = None, respect_robots: bool = True):
        self.data_dir = data_dir or Path(__file__).parent.parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.respect_robots = respect_robots
        self.client = httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-MY,en;q=0.9,en-US;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        )

    def _check_robots(self, url: str) -> bool:
        """Return True if URL is allowed by robots.txt."""
        if not self.respect_robots:
            return True
        rp = _get_robots(url)
        allowed = rp.can_fetch(USER_AGENT, url)
        if not allowed:
            print(f"    BLOCKED by robots.txt: {url}")
        return allowed

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
        """Fetch URL with robots.txt check, httpx first, Firecrawl fallback."""
        if not self._check_robots(url):
            raise RuntimeError(f"Blocked by robots.txt: {url}")
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
