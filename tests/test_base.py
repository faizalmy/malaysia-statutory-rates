"""Tests for the BaseScraper class and module-level functions."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from malaysia_statutory_rates.scrapers.base import (
    BaseScraper,
    CACHE_DIR,
    CACHE_TTL,
    USER_AGENT,
    _get_robots,
)


class ConcreteScraper(BaseScraper):
    """Minimal concrete subclass for testing."""
    SOURCE_URL = "https://example.com/test"
    SOURCE_NAME = "Test Source"

    def scrape(self):
        return {"key": "value"}


# --- _get_robots tests ---

class TestGetRobots:
    @patch("malaysia_statutory_rates.scrapers.base._robots_cache", {})
    @patch("malaysia_statutory_rates.scrapers.base.RobotFileParser")
    def test_get_robots_caches_per_domain(self, mock_rp_cls):
        rp = MagicMock()
        rp.allow_all = True
        mock_rp_cls.return_value = rp
        r1 = _get_robots("https://example.com/page1")
        r2 = _get_robots("https://example.com/page2")
        assert r1 is r2
        assert rp.set_url.call_count == 1

    @patch("malaysia_statutory_rates.scrapers.base._robots_cache", {})
    @patch("malaysia_statutory_rates.scrapers.base.RobotFileParser")
    def test_get_robots_different_domains(self, mock_rp_cls):
        rp = MagicMock()
        rp.allow_all = True
        mock_rp_cls.return_value = rp
        _get_robots("https://example.com/page")
        _get_robots("https://other.com/page")
        assert rp.set_url.call_count == 2

    @patch("malaysia_statutory_rates.scrapers.base._robots_cache", {})
    @patch("malaysia_statutory_rates.scrapers.base.RobotFileParser")
    def test_get_robots_exception_allows_all(self, mock_rp_cls):
        rp = MagicMock()
        rp.set_url.side_effect = Exception("network error")
        mock_rp_cls.return_value = rp
        result = _get_robots("https://example.com/page")
        assert result.allow_all is True

    @patch("malaysia_statutory_rates.scrapers.base._robots_cache", {})
    @patch("malaysia_statutory_rates.scrapers.base.RobotFileParser")
    @patch("malaysia_statutory_rates.scrapers.base.httpx")
    def test_get_robots_cf_challenge_detected(self, mock_httpx, mock_rp_cls):
        rp = MagicMock()
        rp.allow_all = False
        rp.disallow_all = True
        rp.can_fetch.return_value = False
        mock_rp_cls.return_value = rp

        resp = MagicMock()
        resp.headers = {"content-type": "text/html"}
        resp.text = "<html>challenge</html>"
        mock_httpx.get.return_value = resp

        result = _get_robots("https://example.com/page")
        assert result.allow_all is True
        assert result.disallow_all is False

    @patch("malaysia_statutory_rates.scrapers.base._robots_cache", {})
    @patch("malaysia_statutory_rates.scrapers.base.RobotFileParser")
    @patch("malaysia_statutory_rates.scrapers.base.httpx")
    def test_get_robots_no_disallow_rules(self, mock_httpx, mock_rp_cls):
        rp = MagicMock()
        rp.allow_all = False
        rp.disallow_all = True
        rp.can_fetch.return_value = False
        mock_rp_cls.return_value = rp

        resp = MagicMock()
        resp.headers = {"content-type": "text/plain"}
        resp.text = "User-agent: *\nAllow: /"
        mock_httpx.get.return_value = resp

        result = _get_robots("https://example.com/page")
        assert result.allow_all is True

    @patch("malaysia_statutory_rates.scrapers.base._robots_cache", {})
    @patch("malaysia_statutory_rates.scrapers.base.RobotFileParser")
    @patch("malaysia_statutory_rates.scrapers.base.httpx")
    def test_get_robots_httpx_exception_fallback(self, mock_httpx, mock_rp_cls):
        rp = MagicMock()
        rp.allow_all = False
        rp.disallow_all = True
        rp.can_fetch.return_value = False
        mock_rp_cls.return_value = rp
        mock_httpx.get.side_effect = Exception("timeout")

        result = _get_robots("https://example.com/page")
        assert result.allow_all is True


# --- BaseScraper init tests ---

class TestBaseScraperInit:
    def test_default_data_dir(self, tmp_path):
        scraper = ConcreteScraper()
        assert scraper.data_dir.exists()

    def test_custom_data_dir(self, tmp_data_dir):
        scraper = ConcreteScraper(data_dir=tmp_data_dir)
        assert scraper.data_dir == tmp_data_dir
        assert tmp_data_dir.exists()

    def test_respect_robots_default(self, tmp_path):
        scraper = ConcreteScraper(data_dir=tmp_path)
        assert scraper.respect_robots is True

    def test_respect_robots_false(self, tmp_path):
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=False)
        assert scraper.respect_robots is False

    def test_httpx_client_created(self, tmp_path):
        scraper = ConcreteScraper(data_dir=tmp_path)
        assert scraper.client is not None


# --- _check_robots tests ---

class TestCheckRobots:
    def test_check_robots_returns_true_when_not_respecting(self, tmp_path):
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=False)
        assert scraper._check_robots("https://example.com/page") is True

    @patch("malaysia_statutory_rates.scrapers.base._get_robots")
    def test_check_robots_allowed(self, mock_get_robots, tmp_path):
        rp = MagicMock()
        rp.can_fetch.return_value = True
        mock_get_robots.return_value = rp
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=True)
        assert scraper._check_robots("https://example.com/page") is True

    @patch("malaysia_statutory_rates.scrapers.base._get_robots")
    def test_check_robots_blocked(self, mock_get_robots, tmp_path, capsys):
        rp = MagicMock()
        rp.can_fetch.return_value = False
        mock_get_robots.return_value = rp
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=True)
        assert scraper._check_robots("https://example.com/page") is False
        captured = capsys.readouterr()
        assert "BLOCKED" in captured.out


# --- Cache tests ---

class TestCache:
    def test_cache_key_deterministic(self, tmp_path):
        scraper = ConcreteScraper(data_dir=tmp_path)
        k1 = scraper._cache_key("https://example.com/page")
        k2 = scraper._cache_key("https://example.com/page")
        assert k1 == k2

    def test_cache_key_different_urls(self, tmp_path):
        scraper = ConcreteScraper(data_dir=tmp_path)
        k1 = scraper._cache_key("https://example.com/a")
        k2 = scraper._cache_key("https://example.com/b")
        assert k1 != k2

    def test_cache_put_and_get(self, tmp_path, monkeypatch):
        monkeypatch.setattr("malaysia_statutory_rates.scrapers.base.CACHE_DIR", tmp_path / "cache")
        scraper = ConcreteScraper(data_dir=tmp_path)
        scraper._cache_put("https://example.com/page", "<html>cached</html>")
        result = scraper._cache_get("https://example.com/page")
        assert result == "<html>cached</html>"

    def test_cache_get_missing_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr("malaysia_statutory_rates.scrapers.base.CACHE_DIR", tmp_path / "cache")
        scraper = ConcreteScraper(data_dir=tmp_path)
        result = scraper._cache_get("https://nonexistent.com/page")
        assert result is None

    def test_cache_get_expired_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr("malaysia_statutory_rates.scrapers.base.CACHE_DIR", tmp_path / "cache")
        scraper = ConcreteScraper(data_dir=tmp_path)
        scraper._cache_put("https://example.com/page", "<html>old</html>")
        # Back-date the file
        cache_file = scraper._cache_key("https://example.com/page")
        old_time = time.time() - CACHE_TTL - 100
        import os
        os.utime(cache_file, (old_time, old_time))
        result = scraper._cache_get("https://example.com/page")
        assert result is None
        assert not cache_file.exists()


# --- fetch tests ---

class TestFetch:
    @patch("malaysia_statutory_rates.scrapers.base._get_robots")
    def test_fetch_blocked_by_robots(self, mock_get_robots, tmp_path):
        rp = MagicMock()
        rp.can_fetch.return_value = False
        mock_get_robots.return_value = rp
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=True)
        with pytest.raises(RuntimeError, match="Blocked by robots"):
            scraper.fetch("https://example.com/page")

    def test_fetch_returns_cached(self, tmp_path, monkeypatch):
        monkeypatch.setattr("malaysia_statutory_rates.scrapers.base.CACHE_DIR", tmp_path / "cache")
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=False)
        scraper._cache_put("https://example.com/page", "<html>cached</html>")
        result = scraper.fetch("https://example.com/page")
        assert result == "<html>cached</html>"

    def test_fetch_httpx_success(self, tmp_path):
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=False)
        mock_response = MagicMock()
        mock_response.text = "<html><body>" + "content " * 100 + "</body></html>"
        mock_response.raise_for_status = MagicMock()
        scraper.client = MagicMock()
        scraper.client.get.return_value = mock_response
        result = scraper.fetch("https://example.com/page")
        assert "<html>" in result

    def test_fetch_httpx_403_fallback_firecrawl(self, tmp_path, monkeypatch):
        monkeypatch.setattr("malaysia_statutory_rates.scrapers.base.CACHE_DIR", tmp_path / "cache")
        import httpx as real_httpx
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=False)
        mock_response = MagicMock()
        mock_response.status_code = 403
        error = real_httpx.HTTPStatusError("403", request=MagicMock(), response=mock_response)
        scraper.client = MagicMock()
        scraper.client.get.side_effect = error
        scraper._fetch_firecrawl = MagicMock(return_value="<html>firecrawl</html>")
        result = scraper.fetch("https://example.com/page")
        assert result == "<html>firecrawl</html>"

    def test_fetch_httpx_429_fallback_firecrawl(self, tmp_path, monkeypatch):
        monkeypatch.setattr("malaysia_statutory_rates.scrapers.base.CACHE_DIR", tmp_path / "cache")
        import httpx as real_httpx
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=False)
        mock_response = MagicMock()
        mock_response.status_code = 429
        error = real_httpx.HTTPStatusError("429", request=MagicMock(), response=mock_response)
        scraper.client = MagicMock()
        scraper.client.get.side_effect = error
        scraper._fetch_firecrawl = MagicMock(return_value="<html>firecrawl</html>")
        result = scraper.fetch("https://example.com/page")
        assert result == "<html>firecrawl</html>"

    def test_fetch_httpx_500_raises_after_retries(self, tmp_path, monkeypatch):
        monkeypatch.setattr("malaysia_statutory_rates.scrapers.base.CACHE_DIR", tmp_path / "cache")
        import httpx as real_httpx
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=False)
        mock_response = MagicMock()
        mock_response.status_code = 500
        error = real_httpx.HTTPStatusError("500", request=MagicMock(), response=mock_response)
        scraper.client = MagicMock()
        scraper.client.get.side_effect = error
        with pytest.raises(real_httpx.HTTPStatusError):
            scraper.fetch("https://example.com/page", retries=1)

    def test_fetch_httpx_error_fallback_firecrawl(self, tmp_path, monkeypatch):
        monkeypatch.setattr("malaysia_statutory_rates.scrapers.base.CACHE_DIR", tmp_path / "cache")
        import httpx as real_httpx
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=False)
        scraper.client = MagicMock()
        scraper.client.get.side_effect = real_httpx.HTTPError("connection failed")
        scraper._fetch_firecrawl = MagicMock(return_value="<html>firecrawl</html>")
        result = scraper.fetch("https://example.com/page", retries=1)
        assert result == "<html>firecrawl</html>"

    def test_fetch_spa_detection_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setattr("malaysia_statutory_rates.scrapers.base.CACHE_DIR", tmp_path / "cache")
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=False)
        mock_response = MagicMock()
        mock_response.text = "<html><head><script>app()</script></head><body></body></html>"
        mock_response.raise_for_status = MagicMock()
        scraper.client = MagicMock()
        scraper.client.get.return_value = mock_response
        scraper._fetch_firecrawl = MagicMock(return_value="<html>spa content</html>")
        result = scraper.fetch("https://example.com/page")
        assert result == "<html>spa content</html>"


# --- Firecrawl tests ---

class TestFirecrawl:
    def test_fetch_firecrawl_no_key(self, tmp_path):
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=False)
        scraper._get_firecrawl_key = MagicMock(return_value=None)
        with pytest.raises(RuntimeError, match="no Firecrawl API key"):
            scraper._fetch_firecrawl("https://example.com/page")

    def test_fetch_firecrawl_empty_result(self, tmp_path):
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=False)
        scraper._get_firecrawl_key = MagicMock(return_value="test-key")
        with patch("firecrawl.FirecrawlApp") as mock_app_cls:
            app = MagicMock()
            result = MagicMock()
            result.html = None
            result.markdown = None
            app.scrape_url.return_value = result
            mock_app_cls.return_value = app
            with pytest.raises(RuntimeError, match="empty"):
                scraper._fetch_firecrawl("https://example.com/page")

    def test_fetch_firecrawl_success_html(self, tmp_path):
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=False)
        scraper._get_firecrawl_key = MagicMock(return_value="test-key")
        with patch("firecrawl.FirecrawlApp") as mock_app_cls:
            app = MagicMock()
            result = MagicMock()
            result.html = "<html>firecrawl</html>"
            result.markdown = "# page"
            app.scrape_url.return_value = result
            mock_app_cls.return_value = app
            assert scraper._fetch_firecrawl("https://example.com/page") == "<html>firecrawl</html>"

    def test_fetch_firecrawl_success_markdown_only(self, tmp_path):
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=False)
        scraper._get_firecrawl_key = MagicMock(return_value="test-key")
        with patch("firecrawl.FirecrawlApp") as mock_app_cls:
            app = MagicMock()
            result = MagicMock()
            result.html = None
            result.markdown = "# page content"
            app.scrape_url.return_value = result
            mock_app_cls.return_value = app
            assert scraper._fetch_firecrawl("https://example.com/page") == "# page content"

    def test_get_firecrawl_key_from_env(self, tmp_path, monkeypatch):
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=False)
        monkeypatch.setenv("FIRECRAWL_API_KEY", "my-key")
        assert scraper._get_firecrawl_key() == "my-key"

    def test_get_firecrawl_key_missing(self, tmp_path, monkeypatch):
        scraper = ConcreteScraper(data_dir=tmp_path, respect_robots=False)
        monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
        assert scraper._get_firecrawl_key() is None


# --- save and has_changed tests ---

class TestSaveAndHasChanged:
    def test_save_adds_metadata(self, tmp_data_dir):
        scraper = ConcreteScraper(data_dir=tmp_data_dir)
        path = scraper.save("test.json", {"key": "value"})
        assert path.exists()
        data = json.loads(path.read_text())
        assert "_metadata" in data
        assert data["_metadata"]["source"] == "https://example.com/test"
        assert data["_metadata"]["source_name"] == "Test Source"
        assert data["_metadata"]["scraper_version"] == "0.1.0"
        assert "scraped_at" in data["_metadata"]
        assert data["key"] == "value"

    def test_has_changed_no_existing_file(self, tmp_data_dir):
        scraper = ConcreteScraper(data_dir=tmp_data_dir)
        assert scraper.has_changed("nonexistent.json", {"key": "value"}) is True

    def test_has_changed_same_data(self, tmp_data_dir):
        scraper = ConcreteScraper(data_dir=tmp_data_dir)
        data = {"key": "value"}
        scraper.save("test.json", data.copy())
        assert scraper.has_changed("test.json", {"key": "value"}) is False

    def test_has_changed_different_data(self, tmp_data_dir):
        scraper = ConcreteScraper(data_dir=tmp_data_dir)
        scraper.save("test.json", {"key": "value"})
        assert scraper.has_changed("test.json", {"key": "new_value"}) is True

    def test_has_changed_ignores_metadata(self, tmp_data_dir):
        scraper = ConcreteScraper(data_dir=tmp_data_dir)
        scraper.save("test.json", {"key": "value"})
        new_data = {"key": "value", "_metadata": {"different": True}}
        assert scraper.has_changed("test.json", new_data) is False


# --- Context manager tests ---

class TestContextManager:
    def test_context_manager_enter_returns_self(self, tmp_path):
        scraper = ConcreteScraper(data_dir=tmp_path)
        with scraper as s:
            assert s is scraper

    def test_context_manager_exit_closes(self, tmp_path):
        scraper = ConcreteScraper(data_dir=tmp_path)
        scraper.client = MagicMock()
        with scraper:
            pass
        scraper.client.close.assert_called_once()

    def test_close_calls_client_close(self, tmp_path):
        scraper = ConcreteScraper(data_dir=tmp_path)
        scraper.client = MagicMock()
        scraper.close()
        scraper.client.close.assert_called_once()


# --- scrape raises NotImplementedError ---

class TestScrapeNotImplemented:
    def test_base_scrape_raises(self, tmp_path):
        scraper = BaseScraper(data_dir=tmp_path)
        with pytest.raises(NotImplementedError):
            scraper.scrape()


# --- USER_AGENT ---

class TestUserAgent:
    def test_user_agent_contains_package_name(self):
        assert "malaysia-statutory-rates" in USER_AGENT
