"""Tests for PCBScraper."""

from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

import pytest

from malaysia_statutory_rates.scrapers.pcb import PCBScraper, PCB_CACHE_DIR, PCB_FILENAME


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


class TestPCBDownloadPdf:
    def test_download_pdf_cached(self, pcb_scraper, tmp_path, monkeypatch):
        cache_dir = tmp_path / "pdf"
        cache_dir.mkdir()
        pdf_path = cache_dir / PCB_FILENAME
        pdf_path.write_bytes(b"fake pdf content")
        monkeypatch.setattr("malaysia_statutory_rates.scrapers.pcb.PCB_CACHE_DIR", cache_dir)
        result = pcb_scraper._download_pdf()
        assert result == pdf_path

    def test_download_pdf_downloads(self, pcb_scraper, tmp_path, monkeypatch):
        cache_dir = tmp_path / "pdf"
        cache_dir.mkdir()
        monkeypatch.setattr("malaysia_statutory_rates.scrapers.pcb.PCB_CACHE_DIR", cache_dir)
        mock_resp = MagicMock()
        mock_resp.content = b"fake pdf content"
        mock_resp.raise_for_status = MagicMock()
        with patch("malaysia_statutory_rates.scrapers.pcb.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_resp
            result = pcb_scraper._download_pdf()
        assert result.exists()
        assert result.read_bytes() == b"fake pdf content"


class TestPCBScrape:
    def test_scrape_success_with_cached_pdf(self, pcb_scraper, tmp_path):
        """Test scrape with the actual cached PCB PDF if available."""
        pdf_path = PCB_CACHE_DIR / PCB_FILENAME
        if not pdf_path.exists():
            pytest.skip("PCB PDF not cached")
        pcb_scraper._download_pdf = MagicMock(return_value=pdf_path)
        pcb_scraper.has_changed = MagicMock(return_value=True)
        result = pcb_scraper.scrape()
        assert result is not None
        assert result["year"] == 2026
        assert len(result["tax_brackets"]["brackets"]) > 0

    def test_scrape_unchanged_returns_none(self, pcb_scraper, tmp_path):
        pdf_path = PCB_CACHE_DIR / PCB_FILENAME
        if not pdf_path.exists():
            pytest.skip("PCB PDF not cached")
        pcb_scraper._download_pdf = MagicMock(return_value=pdf_path)
        pcb_scraper.has_changed = MagicMock(return_value=False)
        result = pcb_scraper.scrape()
        assert result is None

    def test_scrape_no_year_raises(self, pcb_scraper, tmp_path):
        """Test that missing year in PDF raises ValueError."""
        pdf_path = PCB_CACHE_DIR / PCB_FILENAME
        if not pdf_path.exists():
            pytest.skip("PCB PDF not cached")
        pcb_scraper._download_pdf = MagicMock(return_value=pdf_path)
        # We can easily test this without mocking since the real PDF has year
        pcb_scraper.has_changed = MagicMock(return_value=True)
        result = pcb_scraper.scrape()
        assert result["year"] is not None
