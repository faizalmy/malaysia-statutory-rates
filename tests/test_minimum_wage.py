"""Tests for minimum wage data and scraper."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def test_minimum_wage_file_exists():
    path = DATA_DIR / "minimum_wage.json"
    assert path.exists(), "minimum_wage.json not found"


def test_minimum_wage_schema():
    data = json.loads((DATA_DIR / "minimum_wage.json").read_text())

    assert "source" in data
    assert "year" in data
    assert "effective_from" in data
    assert "rates" in data
    assert "_metadata" in data


def test_minimum_wage_values():
    data = json.loads((DATA_DIR / "minimum_wage.json").read_text())

    assert data["rates"]["nationwide"]["monthly"] == 1700
    assert data["rates"]["nationwide"]["hourly"] == 8.72
    assert data["effective_from"] == "2025-02-01"


def test_minimum_wage_metadata():
    data = json.loads((DATA_DIR / "minimum_wage.json").read_text())

    meta = data["_metadata"]
    assert "scraped_at" in meta
    assert "source" in meta
    assert meta["scraper_version"] == "0.1.0"
