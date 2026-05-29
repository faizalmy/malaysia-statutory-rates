"""Tests for foreign worker rates."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def test_foreign_worker_file_exists():
    assert (DATA_DIR / "foreign_worker_rates.json").exists()


def test_foreign_worker_schema():
    data = json.loads((DATA_DIR / "foreign_worker_rates.json").read_text())
    assert "epf" in data
    assert "socso" in data
    assert "eis" in data
    assert "year" in data
    assert "notes" in data
    assert "_metadata" in data


def test_foreign_worker_epf_rates():
    data = json.loads((DATA_DIR / "foreign_worker_rates.json").read_text())
    epf = data["epf"]
    assert epf["non_malaysian_after_aug98"]["employee"]["rate"] == 0.02
    assert epf["non_malaysian_after_aug98"]["employer"]["rate"] == 0.02


def test_foreign_worker_socso_employment_injury_only():
    data = json.loads((DATA_DIR / "foreign_worker_rates.json").read_text())
    socso = data["socso"]
    assert socso["employment_injury"]["employer_only"] is True


def test_foreign_worker_has_metadata():
    data = json.loads((DATA_DIR / "foreign_worker_rates.json").read_text())
    assert "_metadata" in data
    assert "scraped_at" in data["_metadata"]


def test_foreign_worker_epf_before_aug98():
    data = json.loads((DATA_DIR / "foreign_worker_rates.json").read_text())
    epf = data["epf"]
    assert epf["non_malaysian_before_aug98_below_60"]["employee"]["rate"] == 0.11
    assert epf["non_malaysian_before_aug98_60_plus"]["employee"]["rate"] == 0.055


def test_foreign_worker_notes():
    data = json.loads((DATA_DIR / "foreign_worker_rates.json").read_text())
    assert len(data["notes"]) >= 3
