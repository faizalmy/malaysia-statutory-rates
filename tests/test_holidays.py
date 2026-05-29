"""Tests for public holidays data."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def test_holidays_file_exists():
    assert (DATA_DIR / "public_holidays.json").exists()


def test_holidays_schema():
    data = json.loads((DATA_DIR / "public_holidays.json").read_text())
    assert "national" in data
    assert "state" in data
    assert "year" in data
    assert "_metadata" in data


def test_holidays_has_key_national_days():
    data = json.loads((DATA_DIR / "public_holidays.json").read_text())
    national_dates = {h["date"] for h in data["national"]}
    # Key holidays
    assert "2026-01-01" in national_dates  # New Year
    assert "2026-08-31" in national_dates  # Merdeka
    assert "2026-09-16" in national_dates  # Malaysia Day
    assert "2026-12-25" in national_dates  # Christmas


def test_holidays_has_state_data():
    data = json.loads((DATA_DIR / "public_holidays.json").read_text())
    assert len(data["state"]) >= 10  # At least 10 states
    assert "johor" in data["state"]
    assert "selangor" in data["state"]
    assert "sabah" in data["state"]


def test_holidays_entry_format():
    data = json.loads((DATA_DIR / "public_holidays.json").read_text())
    for h in data["national"]:
        assert "date" in h
        assert "name" in h
        assert h["date"].startswith("2026-")
