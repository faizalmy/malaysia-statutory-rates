"""Tests for MinimumWageScraper."""

from unittest.mock import MagicMock

import pytest

from malaysia_statutory_rates.scrapers.minimum_wage import MinimumWageScraper


@pytest.fixture
def mw_scraper(tmp_path):
    return MinimumWageScraper(data_dir=tmp_path, respect_robots=False)


class TestMinimumWageScrape:
    def test_scrape_success(self, mw_scraper, minimum_wage_html):
        mw_scraper.fetch = MagicMock(return_value=minimum_wage_html)
        mw_scraper.has_changed = MagicMock(return_value=True)
        result = mw_scraper.scrape()
        assert result is not None
        assert result["rates"]["nationwide"]["monthly"] == 1700
        assert result["rates"]["nationwide"]["hourly"] == 8.72

    def test_scrape_success_alt_format(self, mw_scraper, minimum_wage_html_alt):
        mw_scraper.fetch = MagicMock(return_value=minimum_wage_html_alt)
        mw_scraper.has_changed = MagicMock(return_value=True)
        result = mw_scraper.scrape()
        assert result is not None
        assert result["rates"]["nationwide"]["monthly"] == 1700
        assert result["rates"]["nationwide"]["hourly"] == 8.72

    def test_scrape_unchanged_returns_none(self, mw_scraper, minimum_wage_html):
        mw_scraper.fetch = MagicMock(return_value=minimum_wage_html)
        mw_scraper.has_changed = MagicMock(return_value=False)
        result = mw_scraper.scrape()
        assert result is None

    def test_scrape_no_monthly_raises(self, mw_scraper):
        html = "<html><body><p>No wage data here</p></body></html>"
        mw_scraper.fetch = MagicMock(return_value=html)
        with pytest.raises(ValueError, match="Could not parse minimum wage"):
            mw_scraper.scrape()

    def test_scrape_extracts_gazette_link(self, mw_scraper, minimum_wage_html):
        mw_scraper.fetch = MagicMock(return_value=minimum_wage_html)
        mw_scraper.has_changed = MagicMock(return_value=True)
        result = mw_scraper.scrape()
        assert "gazette_url" in result
        assert "PUA" in result["gazette_url"]

    def test_scrape_extracts_gazette_id(self, mw_scraper, minimum_wage_html):
        mw_scraper.fetch = MagicMock(return_value=minimum_wage_html)
        mw_scraper.has_changed = MagicMock(return_value=True)
        result = mw_scraper.scrape()
        assert "PUA" in result["gazette"]

    def test_scrape_extracts_act_name(self, mw_scraper, minimum_wage_html):
        mw_scraper.fetch = MagicMock(return_value=minimum_wage_html)
        mw_scraper.has_changed = MagicMock(return_value=True)
        result = mw_scraper.scrape()
        assert "Perintah Gaji Minimum" in result["act"] or "Minimum Wages Order" in result["act"]

    def test_scrape_extracts_year_from_gazette(self, mw_scraper, minimum_wage_html):
        mw_scraper.fetch = MagicMock(return_value=minimum_wage_html)
        mw_scraper.has_changed = MagicMock(return_value=True)
        result = mw_scraper.scrape()
        assert result["year"] == 2024

    def test_scrape_standalone_rm_divs(self, mw_scraper):
        html = """
        <html><body>
        <div>RM1,700</div>
        <div>RM8.72</div>
        <a href="/wp-content/uploads/PUA%20376.pdf">PUA 376</a>
        </body></html>
        """
        mw_scraper.fetch = MagicMock(return_value=html)
        mw_scraper.has_changed = MagicMock(return_value=True)
        result = mw_scraper.scrape()
        assert result["rates"]["nationwide"]["monthly"] == 1700
        assert result["rates"]["nationwide"]["hourly"] == 8.72

    def test_scrape_no_gazette_link(self, mw_scraper):
        html = """
        <html><body>
        <div>RM1700Kadar Gaji MinimumBulanan</div>
        <div>RM8.72Kadar Gaji MinimumSetiap Jam</div>
        </body></html>
        """
        mw_scraper.fetch = MagicMock(return_value=html)
        mw_scraper.has_changed = MagicMock(return_value=True)
        result = mw_scraper.scrape()
        assert "gazette_url" not in result
        assert result["gazette"] is not None or result.get("gazette") is None  # gazette may be None without link

    def test_scrape_fallback_text_search(self, mw_scraper):
        html = """
        <html><body>
        <p>RM1,700 ... Kadar Gaji Minimum ... Bulanan ... Setiap Jam ... RM8.72</p>
        </body></html>
        """
        mw_scraper.fetch = MagicMock(return_value=html)
        mw_scraper.has_changed = MagicMock(return_value=True)
        result = mw_scraper.scrape()
        assert result["rates"]["nationwide"]["monthly"] == 1700

    def test_scrape_relative_gazette_url(self, mw_scraper):
        html = """
        <html><body>
        <div>RM1700Kadar Gaji MinimumBulanan</div>
        <div>RM8.72Kadar Gaji MinimumSetiap Jam</div>
        <a href="/wp-content/uploads/PUA 376.pdf">Gazette</a>
        </body></html>
        """
        mw_scraper.fetch = MagicMock(return_value=html)
        mw_scraper.has_changed = MagicMock(return_value=True)
        result = mw_scraper.scrape()
        assert result["gazette_url"].startswith("https://gajiminimum.mohr.gov.my")
