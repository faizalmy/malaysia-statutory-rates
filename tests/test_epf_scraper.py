"""Tests for EPFScraper."""

from unittest.mock import MagicMock

import pytest

from malaysia_statutory_rates.scrapers.epf import EPFScraper


@pytest.fixture
def epf_scraper(tmp_path):
    return EPFScraper(data_dir=tmp_path, respect_robots=False)


class TestEPFScrape:
    def test_scrape_success(self, epf_scraper, epf_html):
        epf_scraper.fetch = MagicMock(return_value=epf_html)
        epf_scraper.has_changed = MagicMock(return_value=True)
        result = epf_scraper.scrape()
        assert result is not None
        assert "rates" in result
        assert result["year"] == 2025
        assert result["effective_from"] == "2025-10-01"
        assert "third_schedule" in result.get("third_schedule_pdf", "").lower() or result["third_schedule_pdf"] is not None

    def test_scrape_unchanged_returns_none(self, epf_scraper, epf_html):
        epf_scraper.fetch = MagicMock(return_value=epf_html)
        epf_scraper.has_changed = MagicMock(return_value=False)
        result = epf_scraper.scrape()
        assert result is None

    def test_scrape_no_rates_raises(self, epf_scraper):
        html = "<html><body><table><tr><th>No data</th></tr></table></body></html>"
        epf_scraper.fetch = MagicMock(return_value=html)
        with pytest.raises(ValueError, match="Could not parse EPF rates"):
            epf_scraper.scrape()

    def test_scrape_extracts_malaysian_60_plus(self, epf_scraper, epf_html):
        epf_scraper.fetch = MagicMock(return_value=epf_html)
        epf_scraper.has_changed = MagicMock(return_value=True)
        result = epf_scraper.scrape()
        assert "malaysian_60_plus" in result["rates"]

    def test_scrape_extracts_non_malaysian_after_aug98(self, epf_scraper, epf_html):
        epf_scraper.fetch = MagicMock(return_value=epf_html)
        epf_scraper.has_changed = MagicMock(return_value=True)
        result = epf_scraper.scrape()
        assert "non_malaysian_after_aug98" in result["rates"]


class TestEPFExtractRate:
    def test_extract_employee_rate(self, epf_scraper):
        text = "Employer's share: 13% | Employee's share: 11%"
        assert epf_scraper._extract_rate(text, "employee") == 0.11

    def test_extract_employer_rate(self, epf_scraper):
        text = "Employer's share: 13% | Employee's share: 11%"
        assert epf_scraper._extract_rate(text, "employer") == 0.13

    def test_extract_rate_not_found(self, epf_scraper):
        text = "No rate info here"
        assert epf_scraper._extract_rate(text, "employee") is None

    def test_extract_rate_zero(self, epf_scraper):
        text = "Employee's share: 0%"
        assert epf_scraper._extract_rate(text, "employee") == 0.0

    def test_extract_rate_decimal(self, epf_scraper):
        text = "Employee's share: 11.5%"
        assert epf_scraper._extract_rate(text, "employee") == 0.115


class TestEPFExtractYear:
    def test_extract_year_from_effective_date(self, epf_scraper):
        text = "Effective 1 October 2025, the rates apply"
        assert epf_scraper._extract_year(text) == 2025

    def test_extract_year_fallback(self, epf_scraper):
        text = "Some text about october 2024 rates"
        assert epf_scraper._extract_year(text) == 2024

    def test_extract_year_raises(self, epf_scraper):
        with pytest.raises(ValueError, match="Could not extract year"):
            epf_scraper._extract_year("No year here")


class TestEPFExtractEffectiveFrom:
    def test_extract_effective_full_date(self, epf_scraper):
        text = "effective for 1 October 2025"
        result = epf_scraper._extract_effective_from(text)
        assert result == "2025-10-01"

    def test_extract_effective_month_year(self, epf_scraper):
        text = "effective October 2025"
        result = epf_scraper._extract_effective_from(text)
        assert result == "2025-10-01"

    def test_extract_effective_raises(self, epf_scraper):
        with pytest.raises(ValueError, match="Could not extract effective date"):
            epf_scraper._extract_effective_from("No date here")


class TestEPFExtractAct:
    def test_extract_act_with_section(self, epf_scraper):
        text = "Under EPF Act 1991, Section 43(1), the Third Schedule applies"
        result = epf_scraper._extract_act(text)
        assert "EPF Act 1991" in result
        assert "Section 43(1)" in result
        assert "Third Schedule" in result

    def test_extract_act_without_section(self, epf_scraper):
        text = "EPF Act 1991 governs contributions"
        result = epf_scraper._extract_act(text)
        assert "EPF Act 1991" in result
        assert "Third Schedule" in result

    def test_extract_act_raises(self, epf_scraper):
        with pytest.raises(ValueError, match="Could not extract act"):
            epf_scraper._extract_act("No act reference")


class TestEPFExtractAgeLimits:
    def test_extract_age_limits(self, epf_scraper):
        text = "The minimum age for EPF contribution is age 16 and maximum age is of 75 years old"
        result = epf_scraper._extract_age_limits(text)
        assert result["min_contribution_age"] == 16
        assert result["max_contribution_age"] == 75

    def test_extract_age_limits_raises(self, epf_scraper):
        with pytest.raises(ValueError, match="Could not extract age limits"):
            epf_scraper._extract_age_limits("No age info")


class TestEPFParseWageComponents:
    def test_parse_wage_components(self, epf_scraper, epf_html):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(epf_html, "html.parser")
        included, excluded = epf_scraper._parse_wage_components(soup)
        assert len(included) >= 2
        assert len(excluded) >= 2

    def test_parse_wage_components_empty(self, epf_scraper):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        included, excluded = epf_scraper._parse_wage_components(soup)
        assert included == []
        assert excluded == []


class TestEPFParseNotes:
    def test_parse_notes(self, epf_scraper, epf_html):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(epf_html, "html.parser")
        notes = epf_scraper._parse_notes(soup)
        assert len(notes) > 0

    def test_parse_notes_empty(self, epf_scraper):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        notes = epf_scraper._parse_notes(soup)
        assert notes == []
