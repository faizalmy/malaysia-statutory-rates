"""Tests for pdf_parser module."""

import pytest

from malaysia_statutory_rates.scrapers.pdf_parser import (
    _parse_amount,
    _extract_table,
    _find_table_pages,
    get_booklet_path,
    extract_socso_table,
    extract_eis_table,
    BOOKLET_CACHE_DIR,
    BOOKLET_URL,
)


class TestParseAmount:
    def test_parse_rm_simple(self):
        assert _parse_amount("RM1.10") == 1.1

    def test_parse_rm_integer(self):
        assert _parse_amount("RM40") == 40.0

    def test_parse_rm_with_commas(self):
        assert _parse_amount("RM1,234.50") == 1234.5

    def test_parse_rm_with_spaces(self):
        assert _parse_amount("RM1 234") == 1234.0

    def test_parse_cents(self):
        assert _parse_amount("40 cents") == 0.4

    def test_parse_cent(self):
        assert _parse_amount("1 cent") == 0.01

    def test_parse_cents_case_insensitive(self):
        assert _parse_amount("50 CENTS") == 0.5

    def test_parse_none_for_invalid(self):
        assert _parse_amount("not a number") is None

    def test_parse_none_for_empty(self):
        assert _parse_amount("") is None


class TestGetBookletPath:
    def test_get_booklet_path_returns_pdf(self):
        path = get_booklet_path()
        assert str(path).endswith(".pdf")

    def test_get_booklet_path_in_cache_dir(self):
        path = get_booklet_path()
        assert str(path).startswith(str(BOOKLET_CACHE_DIR))


class TestFindTablePages:
    def test_find_act4_pages_from_cached_pdf(self):
        import fitz
        path = get_booklet_path()
        if not path.exists():
            pytest.skip("PERKESO booklet not cached")
        doc = fitz.open(path)
        from malaysia_statutory_rates.scrapers.pdf_parser import _ACT4_HEADER
        start, end = _find_table_pages(doc, _ACT4_HEADER, num_cols=4)
        doc.close()
        assert start >= 0
        assert end > start

    def test_find_act800_pages_from_cached_pdf(self):
        import fitz
        path = get_booklet_path()
        if not path.exists():
            pytest.skip("PERKESO booklet not cached")
        doc = fitz.open(path)
        from malaysia_statutory_rates.scrapers.pdf_parser import _ACT800_HEADER
        start, end = _find_table_pages(doc, _ACT800_HEADER, num_cols=3)
        doc.close()
        assert start >= 0
        assert end > start


class TestExtractSocsoTable:
    def test_extract_socso_table_from_cached_pdf(self):
        path = get_booklet_path()
        if not path.exists():
            pytest.skip("PERKESO booklet not cached")
        table = extract_socso_table()
        assert len(table) > 0
        assert "row" in table[0]
        assert "wage_min" in table[0]
        assert "wage_max" in table[0]
        assert "employer_schedule1" in table[0]
        assert "employee_schedule1" in table[0]
        assert "total_schedule1" in table[0]
        assert "total_schedule2" in table[0]

    def test_extract_socso_table_from_doc(self):
        import fitz
        path = get_booklet_path()
        if not path.exists():
            pytest.skip("PERKESO booklet not cached")
        doc = fitz.open(path)
        table = extract_socso_table(doc=doc)
        doc.close()
        assert len(table) > 0

    def test_extract_socso_table_file_not_found(self, monkeypatch):
        monkeypatch.setattr(
            "malaysia_statutory_rates.scrapers.pdf_parser.get_booklet_path",
            lambda: Path("/nonexistent/booklet.pdf"),
        )
        with pytest.raises(FileNotFoundError):
            extract_socso_table()

    def test_extract_socso_table_first_row_wages(self):
        path = get_booklet_path()
        if not path.exists():
            pytest.skip("PERKESO booklet not cached")
        table = extract_socso_table()
        assert table[0]["wage_min"] == 0
        assert table[0]["wage_max"] == 30


class TestExtractEisTable:
    def test_extract_eis_table_from_cached_pdf(self):
        path = get_booklet_path()
        if not path.exists():
            pytest.skip("PERKESO booklet not cached")
        table = extract_eis_table()
        assert len(table) > 0
        assert "row" in table[0]
        assert "wage_min" in table[0]
        assert "wage_max" in table[0]
        assert "employer" in table[0]
        assert "employee" in table[0]
        assert "total" in table[0]

    def test_extract_eis_table_from_doc(self):
        import fitz
        path = get_booklet_path()
        if not path.exists():
            pytest.skip("PERKESO booklet not cached")
        doc = fitz.open(path)
        table = extract_eis_table(doc=doc)
        doc.close()
        assert len(table) > 0

    def test_extract_eis_table_file_not_found(self, monkeypatch):
        monkeypatch.setattr(
            "malaysia_statutory_rates.scrapers.pdf_parser.get_booklet_path",
            lambda: Path("/nonexistent/booklet.pdf"),
        )
        with pytest.raises(FileNotFoundError):
            extract_eis_table()

    def test_extract_eis_table_first_row_wages(self):
        path = get_booklet_path()
        if not path.exists():
            pytest.skip("PERKESO booklet not cached")
        table = extract_eis_table()
        assert table[0]["wage_min"] == 0
        assert table[0]["wage_max"] == 30


# Need to import Path for the monkeypatch test
from pathlib import Path
