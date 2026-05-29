"""Tests for PCBScraper."""

from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

from malaysia_statutory_rates.scrapers.pcb import PCBScraper, PCB_CACHE_DIR, _pcb_cache_path


@pytest.fixture
def pcb_scraper(tmp_path):
    return PCBScraper(data_dir=tmp_path, respect_robots=False)


class TestPCBParseInt:
    def test_parse_int_simple(self, pcb_scraper):
        assert pcb_scraper._parse_int("1234") == 1234

    def test_parse_int_with_commas(self, pcb_scraper):
        assert pcb_scraper._parse_int("1,234") == 1234

    def test_parse_int_with_dot(self, pcb_scraper):
        assert pcb_scraper._parse_int("1234.00") == 123400  # strips dot

    def test_parse_int_with_spaces(self, pcb_scraper):
        assert pcb_scraper._parse_int(" 1234 ") == 1234


class TestPCBExtractBrackets:
    def test_extract_brackets_basic(self, pcb_scraper):
        page_text = """
        5,001 - 20,000   5,000   1   - 400   - 800
        20,001 - 35,000  15,000   3   750   1,500
        Exceeding 100,000  65,000  24  10,000  20,000
        """
        brackets = pcb_scraper._extract_brackets(page_text)
        assert len(brackets) >= 2
        # Check first bracket
        assert brackets[0]["min"] == 5001
        assert brackets[0]["max"] == 20000
        assert brackets[0]["rate"] == 0.01
        assert brackets[0]["M"] == 5000

    def test_extract_brackets_exceeding(self, pcb_scraper):
        page_text = "Exceeding 100,000  65,000  24  10,000  20,000"
        brackets = pcb_scraper._extract_brackets(page_text)
        assert len(brackets) == 1
        assert brackets[0]["min"] == 100000
        assert brackets[0]["max"] is None
        assert brackets[0]["rate"] == 0.24

    def test_extract_brackets_empty(self, pcb_scraper):
        brackets = pcb_scraper._extract_brackets("No data here")
        assert brackets == []

    def test_extract_brackets_calculates_base_tax(self, pcb_scraper):
        page_text = """
        5,001 - 20,000   5,000   1   - 400   - 800
        20,001 - 35,000  15,000   3   750   1,500
        """
        brackets = pcb_scraper._extract_brackets(page_text)
        assert brackets[0]["base_tax"] == 0


class TestPCBExtractRebates:
    def test_extract_rebates_basic(self, pcb_scraper):
        page_text = "35,000 and below  14  400  800"
        rebates = pcb_scraper._extract_rebates(page_text)
        assert rebates["threshold"] == 35000
        assert rebates["category_1_3"] == 400
        assert rebates["category_2"] == 800

    def test_extract_rebates_exceeding(self, pcb_scraper):
        page_text = "Exceeding 35,000  0  0  0"
        rebates = pcb_scraper._extract_rebates(page_text)
        assert "above_threshold" in rebates
        assert rebates["above_threshold"]["threshold"] == 35000

    def test_extract_rebates_empty(self, pcb_scraper):
        rebates = pcb_scraper._extract_rebates("No rebate data")
        assert rebates == {}


class TestPCBCachePath:
    def test_cache_path_is_pdf(self):
        path = _pcb_cache_path()
        assert str(path).endswith(".pdf")

    def test_cache_path_in_cache_dir(self):
        path = _pcb_cache_path()
        assert str(path).startswith(str(PCB_CACHE_DIR))


class TestPCBScrape:
    def test_scrape_success_with_cached_pdf(self, pcb_scraper):
        """Test scrape with the actual cached PCB PDF if available."""
        path = _pcb_cache_path()
        if not path.exists():
            # Try old filename
            old = PCB_CACHE_DIR / "pcb-2026-specification.pdf"
            if old.exists():
                path = old
            else:
                pytest.skip("PCB PDF not cached")
        pcb_scraper._download_binary = MagicMock(return_value=path)
        pcb_scraper.has_changed = MagicMock(return_value=True)
        result = pcb_scraper.scrape()
        assert result is not None
        assert result["year"] == 2026
        assert len(result["tax_brackets"]["brackets"]) > 0
        assert "specification_pdf" not in result  # no absolute path in output

    def test_scrape_unchanged_returns_none(self, pcb_scraper):
        path = _pcb_cache_path()
        if not path.exists():
            old = PCB_CACHE_DIR / "pcb-2026-specification.pdf"
            if old.exists():
                path = old
            else:
                pytest.skip("PCB PDF not cached")
        pcb_scraper._download_binary = MagicMock(return_value=path)
        pcb_scraper.has_changed = MagicMock(return_value=False)
        result = pcb_scraper.scrape()
        assert result is None
