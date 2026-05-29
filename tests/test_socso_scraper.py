"""Tests for SOCSOScraper."""

from unittest.mock import MagicMock, patch

import pytest

from malaysia_statutory_rates.scrapers.socso import SOCSOScraper


@pytest.fixture
def socso_scraper(tmp_path):
    return SOCSOScraper(data_dir=tmp_path, respect_robots=False)


class TestSOCSOScrape:
    def test_scrape_success(self, socso_scraper, socso_html):
        socso_scraper.fetch = MagicMock(return_value=socso_html)
        socso_scraper.has_changed = MagicMock(return_value=True)
        with patch("malaysia_statutory_rates.scrapers.socso.extract_socso_table", return_value=[{"row": 1}]):
            result = socso_scraper.scrape()
        assert result is not None
        assert result["act"] == "Employees Social Security Act 1969 (Act 4)"
        assert result["wage_ceiling"] == 6000
        assert result["effective_from"] == "2024-10-01"
        assert result["year"] == 2024

    def test_scrape_unchanged_returns_none(self, socso_scraper, socso_html):
        socso_scraper.fetch = MagicMock(return_value=socso_html)
        socso_scraper.has_changed = MagicMock(return_value=False)
        with patch("malaysia_statutory_rates.scrapers.socso.extract_socso_table", return_value=[]):
            result = socso_scraper.scrape()
        assert result is None

    def test_scrape_no_wage_ceiling_raises(self, socso_scraper):
        html = "<html><body><p>No ceiling info</p></body></html>"
        socso_scraper.fetch = MagicMock(return_value=html)
        with pytest.raises(ValueError, match="wage ceiling"):
            socso_scraper.scrape()

    def test_scrape_no_effective_date_raises(self, socso_scraper):
        html = "<html><body><p>RM6,000 per month</p></body></html>"
        socso_scraper.fetch = MagicMock(return_value=html)
        with pytest.raises(ValueError, match="effective date"):
            socso_scraper.scrape()

    def test_scrape_no_act_raises(self, socso_scraper):
        html = "<html><body><p>RM6,000 per month</p><p>Effective 1 October 2024</p></body></html>"
        socso_scraper.fetch = MagicMock(return_value=html)
        with pytest.raises(ValueError, match="act reference"):
            socso_scraper.scrape()

    def test_scrape_extracts_pdf_links(self, socso_scraper, socso_html):
        socso_scraper.fetch = MagicMock(return_value=socso_html)
        socso_scraper.has_changed = MagicMock(return_value=True)
        with patch("malaysia_statutory_rates.scrapers.socso.extract_socso_table", return_value=[]):
            result = socso_scraper.scrape()
        assert result["pdf_url"] is not None
        assert "ACT4" in result["pdf_url"].upper() or "ACT 4" in result["pdf_url"].upper()

    def test_scrape_extracts_self_employment(self, socso_scraper, socso_html):
        socso_scraper.fetch = MagicMock(return_value=socso_html)
        socso_scraper.has_changed = MagicMock(return_value=True)
        with patch("malaysia_statutory_rates.scrapers.socso.extract_socso_table", return_value=[]):
            result = socso_scraper.scrape()
        assert len(result["self_employment_scheme"]["rates"]) > 0

    def test_scrape_extracts_housewives_scheme(self, socso_scraper, socso_html):
        socso_scraper.fetch = MagicMock(return_value=socso_html)
        socso_scraper.has_changed = MagicMock(return_value=True)
        with patch("malaysia_statutory_rates.scrapers.socso.extract_socso_table", return_value=[]):
            result = socso_scraper.scrape()
        assert result["housewives_scheme"]["act"] == "Act 838"

    def test_scrape_extracts_announcement(self, socso_scraper, socso_html):
        socso_scraper.fetch = MagicMock(return_value=socso_html)
        socso_scraper.has_changed = MagicMock(return_value=True)
        with patch("malaysia_statutory_rates.scrapers.socso.extract_socso_table", return_value=[]):
            result = socso_scraper.scrape()
        assert result["announcement"] != ""

    def test_scrape_rate_table_from_pdf(self, socso_scraper, socso_html):
        socso_scraper.fetch = MagicMock(return_value=socso_html)
        socso_scraper.has_changed = MagicMock(return_value=True)
        rate_table = [{"row": 1, "wage_min": 0, "wage_max": 30}]
        with patch("malaysia_statutory_rates.scrapers.socso.extract_socso_table", return_value=rate_table):
            result = socso_scraper.scrape()
        assert result["rate_table"] == rate_table

    def test_scrape_rate_table_file_not_found(self, socso_scraper, socso_html):
        socso_scraper.fetch = MagicMock(return_value=socso_html)
        socso_scraper.has_changed = MagicMock(return_value=True)
        with patch("malaysia_statutory_rates.scrapers.socso.extract_socso_table", side_effect=FileNotFoundError):
            result = socso_scraper.scrape()
        assert "rate_table" not in result

    def test_scrape_relative_pdf_url(self, socso_scraper):
        html = """
        <html><body>
        <p>RM6,000 per month</p>
        <p>Effective 1 October 2024</p>
        <p>Act 4</p>
        <a href="/images/dokumen/ACT 4.pdf">Act 4 PDF</a>
        </body></html>
        """
        socso_scraper.fetch = MagicMock(return_value=html)
        socso_scraper.has_changed = MagicMock(return_value=True)
        with patch("malaysia_statutory_rates.scrapers.socso.extract_socso_table", return_value=[]):
            result = socso_scraper.scrape()
        assert result["pdf_url"].startswith("https://www.perkeso.gov.my")
