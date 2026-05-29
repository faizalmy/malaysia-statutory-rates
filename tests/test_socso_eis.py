"""Tests for SOCSO and EIS data — match dynamic scraped structure."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


# --- SOCSO ---

def test_socso_file_exists():
    assert (DATA_DIR / "socso_rates.json").exists()


def test_socso_schema():
    data = json.loads((DATA_DIR / "socso_rates.json").read_text())
    assert "schemes" in data
    assert "employment_injury" in data["schemes"]
    assert "invalidity" in data["schemes"]
    assert "wage_ceiling" in data
    assert "_metadata" in data


def test_socso_wage_ceiling():
    data = json.loads((DATA_DIR / "socso_rates.json").read_text())
    assert data["wage_ceiling"] == 6000


def test_socso_has_pdf_link():
    data = json.loads((DATA_DIR / "socso_rates.json").read_text())
    assert data.get("pdf_url"), "SOCSO should have a PDF link to Act 4 rate table"


def test_socso_schemes_exist():
    data = json.loads((DATA_DIR / "socso_rates.json").read_text())
    ei = data["schemes"]["employment_injury"]
    assert ei["employer_only"] is True
    inv = data["schemes"]["invalidity"]
    assert "full_name" in inv


# --- EIS ---

def test_eis_file_exists():
    assert (DATA_DIR / "eis_rates.json").exists()


def test_eis_schema():
    data = json.loads((DATA_DIR / "eis_rates.json").read_text())
    assert "wage_ceiling" in data
    assert "pdf_url" in data
    assert "_metadata" in data


def test_eis_wage_ceiling():
    data = json.loads((DATA_DIR / "eis_rates.json").read_text())
    assert data["wage_ceiling"] == 6000


def test_eis_has_pdf_link():
    data = json.loads((DATA_DIR / "eis_rates.json").read_text())
    assert data.get("pdf_url"), "EIS should have a PDF link to Act 800 rate table"
