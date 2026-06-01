"""Tests for pdf_parser module."""

import fitz
import pytest

from malaysia_statutory_rates.scrapers.pdf_parser import (
    _ACT4_HEADER,
    _ACT800_HEADER,
    _find_table_pages,
    _parse_amount,
    extract_eis_table,
    extract_socso_table,
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


def _get_cached_booklet():
    """Find cached PERKESO booklet PDF."""
    from pathlib import Path
    cache_dir = Path(__file__).parent.parent / ".cache" / "pdf"
    candidates = sorted(cache_dir.glob("*BOOKLET*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    if candidates:
        return candidates[0]
    return None


class TestFindTablePages:
    def test_find_act4_pages(self):
        path = _get_cached_booklet()
        if not path:
            pytest.skip("PERKESO booklet not cached")
        doc = fitz.open(path)
        try:
            start, end = _find_table_pages(doc, _ACT4_HEADER, num_cols=4)
            assert start >= 0
            assert end > start
        finally:
            doc.close()

    def test_find_act800_pages(self):
        path = _get_cached_booklet()
        if not path:
            pytest.skip("PERKESO booklet not cached")
        doc = fitz.open(path)
        try:
            start, end = _find_table_pages(doc, _ACT800_HEADER, num_cols=3)
            assert start >= 0
            assert end > start
        finally:
            doc.close()


class TestExtractSocsoTable:
    def test_extract_socso_table_from_cached_pdf(self):
        path = _get_cached_booklet()
        if not path:
            pytest.skip("PERKESO booklet not cached")
        doc = fitz.open(path)
        try:
            table = extract_socso_table(doc)
        finally:
            doc.close()
        assert len(table) > 0
        assert "row" in table[0]
        assert "wage_min" in table[0]
        assert "wage_max" in table[0]
        assert "employer_schedule1" in table[0]
        assert "employee_schedule1" in table[0]
        assert "total_schedule1" in table[0]
        assert "total_schedule2" in table[0]

    def test_extract_socso_table_first_row_wages(self):
        path = _get_cached_booklet()
        if not path:
            pytest.skip("PERKESO booklet not cached")
        doc = fitz.open(path)
        try:
            table = extract_socso_table(doc)
        finally:
            doc.close()
        assert table[0]["wage_min"] == 0
        assert table[0]["wage_max"] == 30


class TestExtractEisTable:
    def test_extract_eis_table_from_cached_pdf(self):
        path = _get_cached_booklet()
        if not path:
            pytest.skip("PERKESO booklet not cached")
        doc = fitz.open(path)
        try:
            table = extract_eis_table(doc)
        finally:
            doc.close()
        assert len(table) > 0
        assert "row" in table[0]
        assert "wage_min" in table[0]
        assert "wage_max" in table[0]
        assert "employer" in table[0]
        assert "employee" in table[0]
        assert "total" in table[0]

    def test_extract_eis_table_first_row_wages(self):
        path = _get_cached_booklet()
        if not path:
            pytest.skip("PERKESO booklet not cached")
        doc = fitz.open(path)
        try:
            table = extract_eis_table(doc)
        finally:
            doc.close()
        assert table[0]["wage_min"] == 0
        assert table[0]["wage_max"] == 30
