"""Tests for HRDFScraper."""

from unittest.mock import MagicMock

import pytest

from malaysia_statutory_rates.scrapers.hrdf import HRDFScraper


@pytest.fixture
def hrdf_scraper(tmp_path):
    return HRDFScraper(data_dir=tmp_path, respect_robots=False)


class TestHRDFScrape:
    def test_scrape_success(self, hrdf_scraper, hrdf_html):
        hrdf_scraper.fetch = MagicMock(return_value=hrdf_html)
        hrdf_scraper.has_changed = MagicMock(return_value=True)
        result = hrdf_scraper.scrape()
        assert result is not None
        assert "PSMB Act 2001" in result["act"]
        assert result["rates"]["mandatory"]["rate"] == 0.01
        assert result["rates"]["optional"]["rate"] == 0.005

    def test_scrape_unchanged_returns_none(self, hrdf_scraper, hrdf_html):
        hrdf_scraper.fetch = MagicMock(return_value=hrdf_html)
        hrdf_scraper.has_changed = MagicMock(return_value=False)
        result = hrdf_scraper.scrape()
        assert result is None

    def test_scrape_no_mandatory_rate_raises(self, hrdf_scraper):
        html = "<html><body><p>Section 14 — no rate info</p></body></html>"
        hrdf_scraper.fetch = MagicMock(return_value=html)
        with pytest.raises(ValueError, match="mandatory"):
            hrdf_scraper.scrape()

    def test_scrape_no_optional_rate_raises(self, hrdf_scraper):
        html = """
        <html><body>
        <p>Section 14: 1% of the monthly wage(s)</p>
        <p>Section 15 — no rate info</p>
        </body></html>
        """
        hrdf_scraper.fetch = MagicMock(return_value=html)
        with pytest.raises(ValueError, match="optional"):
            hrdf_scraper.scrape()

    def test_scrape_extracts_wage_components(self, hrdf_scraper, hrdf_html):
        hrdf_scraper.fetch = MagicMock(return_value=hrdf_html)
        hrdf_scraper.has_changed = MagicMock(return_value=True)
        result = hrdf_scraper.scrape()
        assert "included" in result["wage_components"]
        assert "excluded" in result["wage_components"]

    def test_scrape_extracts_formula(self, hrdf_scraper, hrdf_html):
        hrdf_scraper.fetch = MagicMock(return_value=hrdf_html)
        hrdf_scraper.has_changed = MagicMock(return_value=True)
        result = hrdf_scraper.scrape()
        assert "LEVY" in result["notes"][0]

    def test_scrape_no_formula_fallback(self, hrdf_scraper):
        html = """
        <html><body>
        <p>PSMB Act 2001</p>
        <p>Section 14: 1% of the monthly wage(s)</p>
        <p>Section 15: 0.5% of the monthly wage(s)</p>
        </body></html>
        """
        hrdf_scraper.fetch = MagicMock(return_value=html)
        hrdf_scraper.has_changed = MagicMock(return_value=True)
        result = hrdf_scraper.scrape()
        assert result["notes"] is not None  # notes list may be empty with simple HTML


class TestHRDFExtractRate:
    def test_extract_rate_section14(self, hrdf_scraper):
        text = "Section 14 — Mandatory HRDF Registration\n1% of the monthly wage(s)"
        assert hrdf_scraper._extract_rate(text, "section 14") == 0.01

    def test_extract_rate_section15(self, hrdf_scraper):
        text = "Section 15 — Voluntary Registration\n0.5% of the monthly wage(s)"
        assert hrdf_scraper._extract_rate(text, "section 15") == 0.005

    def test_extract_rate_broader_pattern(self, hrdf_scraper):
        text = "section 14 ... levy ... 1%"
        assert hrdf_scraper._extract_rate(text, "section 14") == 0.01

    def test_extract_rate_not_found(self, hrdf_scraper):
        text = "No relevant section info"
        assert hrdf_scraper._extract_rate(text, "section 14") is None


class TestHRDFParseWageComponents:
    def test_parse_wage_components_included(self, hrdf_scraper):
        text = "WagesBasic salary and fixed allowance including leave pay and arrears of wages but DOES NOT INCLUDE: -any pension fund"
        included, excluded = hrdf_scraper._parse_wage_components(text)
        assert "Basic salary" in included

    def test_parse_wage_components_excluded(self, hrdf_scraper):
        text = "WagesBasic salary but DOES NOT INCLUDE: -any pension fund -any retrenchment benefit"
        included, excluded = hrdf_scraper._parse_wage_components(text)
        assert len(excluded) > 0

    def test_parse_wage_components_empty(self, hrdf_scraper):
        included, excluded = hrdf_scraper._parse_wage_components("No wage info")
        assert included == []
        assert excluded == []


class TestHRDFFormula:
    def test_parse_formula(self, hrdf_scraper, hrdf_html):
        result = hrdf_scraper._parse_formula(hrdf_html)
        assert result is not None
        assert "LEVY" in result

    def test_parse_formula_not_found(self, hrdf_scraper):
        result = hrdf_scraper._parse_formula("No formula here")
        assert result is None
