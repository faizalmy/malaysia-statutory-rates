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


# --- Rate Tables (from seed data) ---

def test_socso_rate_table_exists():
    data = json.loads((DATA_DIR / "socso_rates.json").read_text())
    assert "rate_table" in data, "SOCSO should include rate_table from Act 4 PDF"
    assert len(data["rate_table"]) == 65, f"Expected 65 brackets, got {len(data['rate_table'])}"


def test_socso_rate_table_structure():
    data = json.loads((DATA_DIR / "socso_rates.json").read_text())
    first = data["rate_table"][0]
    assert first["wage_min"] == 0
    assert first["wage_max"] == 30
    assert first["employer_schedule1"] == 0.4
    assert first["employee_schedule1"] == 0.1
    assert first["total_schedule1"] == 0.5
    assert first["total_schedule2"] == 0.3


def test_socso_rate_table_cap():
    data = json.loads((DATA_DIR / "socso_rates.json").read_text())
    cap = data["rate_table"][-1]
    assert cap["wage_min"] == 6000
    assert cap["wage_max"] is None  # cap row
    assert cap["total_schedule1"] == 133.9
    assert cap["total_schedule2"] == 74.4


def test_socso_rate_table_sums():
    """employer + employee should equal total for each row."""
    data = json.loads((DATA_DIR / "socso_rates.json").read_text())
    for row in data["rate_table"]:
        expected_total = round(row["employer_schedule1"] + row["employee_schedule1"], 2)
        assert abs(row["total_schedule1"] - expected_total) < 0.02, \
            f"Sum mismatch at wage {row['wage_min']}: {row['employer_schedule1']} + {row['employee_schedule1']} != {row['total_schedule1']}"


def test_eis_rate_table_exists():
    data = json.loads((DATA_DIR / "eis_rates.json").read_text())
    assert "rate_table" in data, "EIS should include rate_table from Act 800 PDF"
    assert len(data["rate_table"]) == 65, f"Expected 65 brackets, got {len(data['rate_table'])}"


def test_eis_rate_table_equal_split():
    """EIS employer and employee should be equal."""
    data = json.loads((DATA_DIR / "eis_rates.json").read_text())
    for row in data["rate_table"]:
        assert row["employer"] == row["employee"], \
            f"EIS not equal split at wage {row['wage_min']}: {row['employer']} != {row['employee']}"


def test_eis_rate_table_cap():
    data = json.loads((DATA_DIR / "eis_rates.json").read_text())
    cap = data["rate_table"][-1]
    assert cap["wage_min"] == 6000
    assert cap["wage_max"] is None
    assert cap["employee"] == 11.9
    assert cap["employer"] == 11.9
    assert cap["total"] == 23.8


def test_socso_rate_table_source():
    data = json.loads((DATA_DIR / "socso_rates.json").read_text())
    assert "BOOKLET" in data.get("rate_table_source", "")


def test_eis_rate_table_source():
    data = json.loads((DATA_DIR / "eis_rates.json").read_text())
    assert "BOOKLET" in data.get("rate_table_source", "")
