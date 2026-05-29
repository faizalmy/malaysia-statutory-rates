"""Tests for HRDF data."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def test_hrdf_file_exists():
    assert (DATA_DIR / "hrdf_rates.json").exists()


def test_hrdf_schema():
    data = json.loads((DATA_DIR / "hrdf_rates.json").read_text())
    assert "rates" in data
    assert "mandatory" in data["rates"]
    assert "optional" in data["rates"]
    assert "_metadata" in data


def test_hrdf_values():
    data = json.loads((DATA_DIR / "hrdf_rates.json").read_text())
    assert data["rates"]["mandatory"]["rate"] == 0.01
    assert data["rates"]["optional"]["rate"] == 0.005
    assert data["rates"]["exempted"]["rate"] == 0.0


def test_hrdf_wage_components():
    data = json.loads((DATA_DIR / "hrdf_rates.json").read_text())
    assert "wage_components" in data
    assert "included" in data["wage_components"]
    assert "excluded" in data["wage_components"]
    assert len(data["wage_components"]["included"]) > 0
