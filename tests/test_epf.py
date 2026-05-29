"""Tests for EPF data — match dynamic scraped structure."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def test_epf_file_exists():
    assert (DATA_DIR / "epf_rates.json").exists()


def test_epf_schema():
    data = json.loads((DATA_DIR / "epf_rates.json").read_text())
    assert "rates" in data
    assert "malaysian_pr_nonmy_before_aug98_below_60" in data["rates"]
    assert "malaysian_60_plus" in data["rates"]
    assert "non_malaysian_after_aug98" in data["rates"]
    assert "contribution_method" in data
    assert "_metadata" in data


def test_epf_citizen_below_60():
    data = json.loads((DATA_DIR / "epf_rates.json").read_text())
    rates = data["rates"]["malaysian_pr_nonmy_before_aug98_below_60"]
    assert rates["employee"]["rate"] == 0.11
    assert rates["employer"]["wage_lte_5000"]["rate"] == 0.13
    assert rates["employer"]["wage_gt_5000"]["rate"] == 0.12


def test_epf_citizen_60_plus():
    data = json.loads((DATA_DIR / "epf_rates.json").read_text())
    rates = data["rates"]["malaysian_60_plus"]
    assert rates["employee"]["rate"] == 0.0
    assert rates["employer"]["rate"] == 0.04


def test_epf_foreign_worker():
    data = json.loads((DATA_DIR / "epf_rates.json").read_text())
    rates = data["rates"]["non_malaysian_after_aug98"]
    assert rates["employee"]["rate"] == 0.02
    assert rates["employer"]["rate"] == 0.02


def test_epf_effective_date():
    data = json.loads((DATA_DIR / "epf_rates.json").read_text())
    assert data["effective_from"] == "2025-10-01"
    assert "third_schedule_pdf" in data


def test_epf_age_limits():
    data = json.loads((DATA_DIR / "epf_rates.json").read_text())
    assert data["age_limits"]["min_contribution_age"] == 14
    assert data["age_limits"]["max_contribution_age"] == 75


def test_epf_contribution_method():
    data = json.loads((DATA_DIR / "epf_rates.json").read_text())
    method = data["contribution_method"]
    assert "description" in method
    assert "RM20,000" in method["description"]


def test_epf_has_all_rate_categories():
    """All 4 rate categories must be present from the live scrape."""
    data = json.loads((DATA_DIR / "epf_rates.json").read_text())
    keys = set(data["rates"].keys())
    assert "malaysian_pr_nonmy_before_aug98_below_60" in keys
    assert "malaysian_60_plus" in keys
    assert "pr_nonmy_before_aug98_60_plus" in keys
    assert "non_malaysian_after_aug98" in keys
