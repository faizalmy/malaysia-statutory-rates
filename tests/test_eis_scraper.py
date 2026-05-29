"""Tests for EISScraper."""

from unittest.mock import MagicMock, patch

import pytest

from malaysia_statutory_rates.scrapers.eis import EISScraper


@pytest.fixture
def eis_scraper(tmp_path):
    return EISScraper(data_dir=tmp_path, respect_robots=False)


class TestEISScrape:
    def test_scrape_success(self, eis_scraper, eis_html):
        eis_scraper.fetch = MagicMock(return_value=eis_html)
        eis_scraper.has_changed = MagicMock(return_value=True)
        with patch("malaysia_statutory_rates.scrapers.eis.extract_eis_table", return_value=[{"row": 1}]):
            result = eis_scraper.scrape()
        assert result is not None
        assert result["act"] == "Employment Insurance System Act 2017 (Act 800)"
        assert result["wage_ceiling"] == 6000
        assert result["effective_from"] == "2024-10-01"
        assert result["year"] == 2024

    def test_scrape_unchanged_returns_none(self, eis_scraper, eis_html):
        eis_scraper.fetch = MagicMock(return_value=eis_html)
        eis_scraper.has_changed = MagicMock(return_value=False)
        with patch("malaysia_statutory_rates.scrapers.eis.extract_eis_table", return_value=[]):
            result = eis_scraper.scrape()
        assert result is None

    def test_scrape_no_wage_ceiling_raises(self, eis_scraper):
        html = "<html><body><p>No ceiling info</p></body></html>"
        eis_scraper.fetch = MagicMock(return_value=html)
        with pytest.raises(ValueError, match="wage ceiling"):
            eis_scraper.scrape()

    def test_scrape_no_effective_date_raises(self, eis_scraper):
        html = "<html><body><p>RM6,000 per month</p></body></html>"
        eis_scraper.fetch = MagicMock(return_value=html)
        with pytest.raises(ValueError, match="effective date"):
            eis_scraper.scrape()

    def test_scrape_no_act_raises(self, eis_scraper):
        html = "<html><body><p>RM6,000 per month</p><p>Effective 1 October 2024</p></body></html>"
        eis_scraper.fetch = MagicMock(return_value=html)
        with pytest.raises(ValueError, match="act reference"):
            eis_scraper.scrape()

    def test_scrape_extracts_pdf_link(self, eis_scraper, eis_html):
        eis_scraper.fetch = MagicMock(return_value=eis_html)
        eis_scraper.has_changed = MagicMock(return_value=True)
        with patch("malaysia_statutory_rates.scrapers.eis.extract_eis_table", return_value=[]):
            result = eis_scraper.scrape()
        assert result["pdf_url"] is not None

    def test_scrape_extracts_description(self, eis_scraper, eis_html):
        eis_scraper.fetch = MagicMock(return_value=eis_html)
        eis_scraper.has_changed = MagicMock(return_value=True)
        with patch("malaysia_statutory_rates.scrapers.eis.extract_eis_table", return_value=[]):
            result = eis_scraper.scrape()
        assert result["description"] is not None
        assert "employment insurance" in result["description"].lower() or "0.4%" in result["description"]

    def test_scrape_rate_table_from_pdf(self, eis_scraper, eis_html):
        eis_scraper.fetch = MagicMock(return_value=eis_html)
        eis_scraper.has_changed = MagicMock(return_value=True)
        rate_table = [{"row": 1, "wage_min": 0, "wage_max": 30}]
        with patch("malaysia_statutory_rates.scrapers.eis.extract_eis_table", return_value=rate_table):
            result = eis_scraper.scrape()
        assert result["rate_table"] == rate_table
        assert result["rate_table_source"] is not None

    def test_scrape_rate_table_file_not_found(self, eis_scraper, eis_html):
        eis_scraper.fetch = MagicMock(return_value=eis_html)
        eis_scraper.has_changed = MagicMock(return_value=True)
        with patch("malaysia_statutory_rates.scrapers.eis.extract_eis_table", side_effect=FileNotFoundError):
            result = eis_scraper.scrape()
        assert "rate_table" not in result

    def test_scrape_relative_pdf_url(self, eis_scraper):
        html = """
        <html><body>
        <p>RM6,000 per month</p>
        <p>Effective 1 October 2024</p>
        <p>Act 800</p>
        <p>0.4% Employment Insurance System</p>
        <a href="/images/dokumen/ACT800.pdf">Act 800 PDF</a>
        </body></html>
        """
        eis_scraper.fetch = MagicMock(return_value=html)
        eis_scraper.has_changed = MagicMock(return_value=True)
        with patch("malaysia_statutory_rates.scrapers.eis.extract_eis_table", return_value=[]):
            result = eis_scraper.scrape()
        assert result["pdf_url"].startswith("https://www.perkeso.gov.my")

    def test_scrape_no_pdf_link(self, eis_scraper):
        html = """
        <html><body>
        <p>RM6,000 per month</p>
        <p>Effective 1 October 2024</p>
        <p>Act 800</p>
        <p>0.4% Employment Insurance System</p>
        </body></html>
        """
        eis_scraper.fetch = MagicMock(return_value=html)
        eis_scraper.has_changed = MagicMock(return_value=True)
        with patch("malaysia_statutory_rates.scrapers.eis.extract_eis_table", return_value=[]):
            result = eis_scraper.scrape()
        assert result["pdf_url"] is None
