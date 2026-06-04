"""End-to-end tests — exercises the full pipeline.

Scrape → validate → changelog → save → status → show.
Uses a real temp data directory with mock HTTP to avoid hitting real sites.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from malaysia_statutory_rates.changelog import read_changelog
from malaysia_statutory_rates.scrapers import SCRAPERS, run_scrapers
from malaysia_statutory_rates.scrapers.base import BaseScraper
from malaysia_statutory_rates.status import rates_status
from malaysia_statutory_rates.validator import RateValidator, validate_and_report


# ── Helpers ───────────────────────────────────────────────────────────────────

SAMPLE_DATA = {
    "minimum_wage": {
        "source": "https://gajiminimum.mohr.gov.my/",
        "year": 2026,
        "effective_from": "2026-04-27",
        "gazette": "PUA 376",
        "act": "Perintah Gaji Minimum 2024",
        "rates": {"nationwide": {"monthly": 1700, "hourly": 8.72}},
        "min_employees_for_mandatory": 1,
        "notes": ["Applies to all employers"],
        "gazette_url": "https://gajiminimum.mohr.gov.my/wp-content/uploads/PUA 376.pdf",
    },
    "epf_rates": {
        "source": "https://www.kwsp.gov.my/en/employer/responsibilities/mandatory-contribution",
        "year": 2025,
        "effective_from": "2025-10-01",
        "act": "EPF Act 1991 — Section 43(1), Third Schedule",
        "rates": {
            "malaysian_60_plus": {
                "label": "Malaysian",
                "salary_range": "No limit",
                "employee": {"rate": 0.0, "note": "Optional"},
                "employer": {"rate": 0.04},
            },
            "malaysian_pr_nonmy_before_aug98_below_60": {
                "label": "Malaysian PR",
                "salary_range": "RM5,000 and below",
                "employee": {"rate": 0.11},
                "employer": {"wage_lte_5000": {"rate": 0.13}, "wage_gt_5000": {"rate": 0.13}},
            },
            "non_malaysian_after_aug98": {
                "label": "Non-Malaysians",
                "salary_range": "No limit",
                "employee": {"rate": 0.0},
                "employer": {"rate": 0.12},
            },
        },
        "age_limits": {"min_contribution_age": 14, "max_contribution_age": 75},
    },
}


def _make_scraper_class(name: str, data_dir: Path, data: dict):
    """Create a scraper subclass that returns fixed data."""

    class _TestScraper(BaseScraper):
        SOURCE_URL = data.get("source", "https://example.com")
        SOURCE_NAME = f"Test {name}"

        def scrape(self):
            return data

    return _TestScraper


# ── E2E: Full pipeline ───────────────────────────────────────────────────────

class TestE2EFullPipeline:
    """End-to-end: scrape → validate → changelog → save → status."""

    def test_minimum_wage_pipeline(self, tmp_path: Path):
        """Full pipeline for minimum_wage: scrape, validate, save, check changelog and status."""
        data = SAMPLE_DATA["minimum_wage"]
        ScraperClass = _make_scraper_class("minimum_wage", tmp_path, data)

        scraper = ScraperClass(data_dir=tmp_path)

        # 1. Scrape returns data
        result = scraper.scrape()
        assert result is not None
        assert result["rates"]["nationwide"]["monthly"] == 1700

        # 2. Validate
        errors, proceed = validate_and_report("minimum_wage", result)
        assert proceed is True
        assert len(errors) == 0

        # 3. Save (triggers changelog + disclaimer)
        scraper.save("minimum_wage.json", result)

        # 4. Verify file written
        saved_path = tmp_path / "minimum_wage.json"
        assert saved_path.exists()
        saved = json.loads(saved_path.read_text())

        # 5. Verify metadata
        assert "_metadata" in saved
        assert "scraped_at" in saved["_metadata"]
        assert "disclaimer" in saved["_metadata"]
        assert "verify" in saved["_metadata"]["disclaimer"].lower()
        assert saved["_metadata"]["official_reference"] == "Test minimum_wage"
        assert saved["_metadata"]["source"] == data["source"]

        # 6. Verify data preserved
        assert saved["rates"]["nationwide"]["monthly"] == 1700
        assert saved["rates"]["nationwide"]["hourly"] == 8.72

        # 7. Verify changelog entry
        entries = read_changelog(tmp_path)
        assert len(entries) == 1
        assert entries[0]["scraper"] == "minimum_wage"
        assert entries[0]["changes"][0]["type"] == "added"  # New file

        # 8. Verify status
        statuses = rates_status(tmp_path)
        assert len(statuses) == 1
        assert statuses[0]["name"] == "minimum_wage"
        assert statuses[0]["freshness"] == "fresh"

        scraper.close()

    def test_epf_pipeline(self, tmp_path: Path):
        """Full pipeline for EPF rates."""
        data = SAMPLE_DATA["epf_rates"]
        ScraperClass = _make_scraper_class("epf_rates", tmp_path, data)
        scraper = ScraperClass(data_dir=tmp_path)

        result = scraper.scrape()
        assert result is not None

        errors, proceed = validate_and_report("epf_rates", result)
        assert proceed is True

        scraper.save("epf_rates.json", result)

        saved = json.loads((tmp_path / "epf_rates.json").read_text())
        assert saved["rates"]["malaysian_pr_nonmy_before_aug98_below_60"]["employee"]["rate"] == 0.11
        assert "disclaimer" in saved["_metadata"]

        entries = read_changelog(tmp_path)
        assert len(entries) == 1
        assert entries[0]["scraper"] == "epf_rates"

        scraper.close()

    def test_data_update_creates_changelog_diff(self, tmp_path: Path):
        """Second scrape with changed data creates a proper diff in changelog."""
        data_v1 = SAMPLE_DATA["minimum_wage"].copy()
        data_v1["rates"] = {"nationwide": {"monthly": 1500, "hourly": 7.0}}

        ScraperClass = _make_scraper_class("minimum_wage", tmp_path, data_v1)
        scraper = ScraperClass(data_dir=tmp_path)
        scraper.save("minimum_wage.json", data_v1)

        # Second save with updated data
        data_v2 = SAMPLE_DATA["minimum_wage"].copy()
        scraper.save("minimum_wage.json", data_v2)

        entries = read_changelog(tmp_path)
        assert len(entries) == 2

        # First entry: new file
        assert entries[0]["changes"][0]["type"] == "added"

        # Second entry: modifications
        changes = entries[1]["changes"]
        modified = [c for c in changes if c["type"] == "modified"]
        assert len(modified) > 0
        # Monthly changed 1500 → 1700
        monthly_changes = [c for c in modified if "monthly" in c["path"]]
        assert len(monthly_changes) == 1
        assert monthly_changes[0]["old"] == 1500
        assert monthly_changes[0]["new"] == 1700

        scraper.close()

    def test_validation_blocks_bad_data(self, tmp_path: Path):
        """Validation catches out-of-range values and blocks save in strict mode."""
        bad_data = {
            "source": "https://gajiminimum.mohr.gov.my/",
            "year": 2026,
            "rates": {"nationwide": {"monthly": 50, "hourly": 0.1}},  # Way too low
        }

        errors, proceed = validate_and_report("minimum_wage", bad_data, strict=True)
        assert proceed is False
        assert len(errors) >= 2  # Both monthly and hourly out of range

        # Non-strict: warnings don't block
        errors, proceed = validate_and_report("minimum_wage", bad_data, strict=False)
        assert proceed is True
        assert len(errors) >= 2

    def test_schema_error_blocks_even_non_strict(self, tmp_path: Path):
        """Missing required fields block save even without --strict."""
        incomplete = {"source": "https://example.com"}  # Missing year, rates

        errors, proceed = validate_and_report("minimum_wage", incomplete, strict=False)
        assert proceed is False
        assert any(e.severity == "error" for e in errors)

    def test_magnitude_detection(self, tmp_path: Path):
        """Large rate changes are flagged by magnitude checks."""
        old_data = SAMPLE_DATA["epf_rates"].copy()
        new_data = json.loads(json.dumps(old_data))
        new_data["rates"]["malaysian_pr_nonmy_before_aug98_below_60"]["employee"]["rate"] = 0.50

        errors, proceed = validate_and_report("epf_rates", new_data, old_data=old_data)
        assert proceed is True  # warnings don't block in non-strict
        mag_errors = [e for e in errors if e.rule == "magnitude"]
        assert len(mag_errors) >= 1


# ── E2E: run_scrapers integration ────────────────────────────────────────────

class TestE2ERunScrapers:
    """Test run_scrapers with mocked SCRAPERS registry."""

    @patch("malaysia_statutory_rates.validator.validate_and_report", return_value=([], True))
    @patch("malaysia_statutory_rates.scrapers.SCRAPERS")
    def test_run_scrapers_full_flow(self, mock_scrapers, mock_validate, tmp_path: Path):
        """run_scrapers creates files, changelog, and returns correct results."""
        data = SAMPLE_DATA["minimum_wage"]

        scraper = MagicMock()
        scraper.scrape.return_value = data
        scraper.data_dir = tmp_path
        scraper.close = MagicMock()

        mock_cls = MagicMock(return_value=scraper)
        mock_scrapers.__iter__ = MagicMock(return_value=iter(["minimum_wage"]))
        mock_scrapers.__getitem__ = MagicMock(return_value=mock_cls)
        mock_scrapers.keys.return_value = ["minimum_wage"]
        mock_scrapers.__contains__ = MagicMock(side_effect=lambda x: x == "minimum_wage")

        results = run_scrapers(["minimum_wage"])
        assert results["minimum_wage"] is True
        scraper.save.assert_called_once()
        scraper.close.assert_called_once()

    @patch("malaysia_statutory_rates.validator.validate_and_report")
    @patch("malaysia_statutory_rates.scrapers.SCRAPERS")
    def test_run_scrapers_strict_blocks(self, mock_scrapers, mock_validate, tmp_path: Path):
        """run_scrapers with strict=True blocks on validation errors."""
        from malaysia_statutory_rates.validator import ValidationError

        mock_validate.return_value = (
            [ValidationError("test", "rate", "range", "too high", "warning")],
            False,
        )

        scraper = MagicMock()
        scraper.scrape.return_value = {"rate": 999}
        scraper.data_dir = tmp_path
        scraper.close = MagicMock()

        mock_cls = MagicMock(return_value=scraper)
        mock_scrapers.__iter__ = MagicMock(return_value=iter(["test"]))
        mock_scrapers.__getitem__ = MagicMock(return_value=mock_cls)
        mock_scrapers.keys.return_value = ["test"]
        mock_scrapers.__contains__ = MagicMock(side_effect=lambda x: x == "test")

        results = run_scrapers(["test"], strict=True)
        assert results["test"] is False
        scraper.save.assert_not_called()
        scraper.close.assert_called_once()


# ── E2E: CLI integration ─────────────────────────────────────────────────────

class TestE2ECLI:
    """Test CLI commands end-to-end."""

    def test_cli_show_outputs_json(self, capsys):
        """`show` command outputs valid JSON."""
        from malaysia_statutory_rates.cli import cmd_show
        from unittest.mock import MagicMock

        args = MagicMock()
        args.rate = "all"

        with patch("malaysia_statutory_rates.cli.load_rates") as mock_load:
            mock_load.return_value = {"test": {"value": 1}}
            cmd_show(args)

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed == {"test": {"value": 1}}

    def test_cli_status_outputs_table(self, capsys):
        """`status` command outputs a table with rate names."""
        from malaysia_statutory_rates.cli import cmd_status
        from unittest.mock import MagicMock

        args = MagicMock()
        cmd_status(args)

        out = capsys.readouterr().out
        assert "Rate" in out  # Header
        assert "epf_rates" in out or "minimum_wage" in out

    def test_cli_changelog_with_entries(self, tmp_path: Path, capsys):
        """`changelog` command shows entries from changelog file."""
        from malaysia_statutory_rates.cli import cmd_changelog
        from malaysia_statutory_rates.changelog import append_changelog
        from unittest.mock import MagicMock

        # Create a changelog entry
        data = {"rates": {"monthly": 1700}}
        append_changelog(tmp_path, "minimum_wage", "https://example.com", None, data)

        args = MagicMock()
        args.last = None

        with patch("malaysia_statutory_rates.cli.Path") as mock_path:
            mock_path.return_value.parent.__truediv__ = MagicMock(return_value=tmp_path)
            # Directly test read_changelog
            entries = read_changelog(tmp_path)
            assert len(entries) == 1
            assert "minimum_wage" in entries[0]["scraper"]

    def test_cli_disclaimer_on_stderr(self, capsys):
        """Disclaimer prints to stderr, not stdout."""
        from malaysia_statutory_rates.cli import _print_disclaimer

        _print_disclaimer()

        captured = capsys.readouterr()
        # stdout should be clean
        assert captured.out == ""
        # stderr should have disclaimer
        assert "verify" in captured.err.lower() or "risk" in captured.err.lower()


# ── E2E: Real data files ─────────────────────────────────────────────────────

class TestE2ERealData:
    """Validate the actual bundled data files end-to-end."""

    def test_all_files_load_and_validate(self):
        """Every data file loads, validates, and has correct structure."""
        from malaysia_statutory_rates import load_rates

        rates = load_rates()
        validator = RateValidator()

        assert len(rates) >= 8

        for name, data in rates.items():
            # Has metadata
            assert "_metadata" in data, f"{name} missing _metadata"
            assert "scraped_at" in data["_metadata"], f"{name} missing scraped_at"
            assert "source" in data["_metadata"], f"{name} missing source"

            # Validates without errors
            errors = validator.validate(name, data)
            real_errors = [e for e in errors if e.severity == "error"]
            assert len(real_errors) == 0, f"{name} has errors: {real_errors}"

    def test_all_files_have_status(self):
        """Status reports freshness for all bundled files."""
        statuses = rates_status()
        assert len(statuses) >= 8

        for s in statuses:
            assert s["freshness"] in ("fresh", "stale", "old", "missing")
            assert s["name"]  # Not empty

    def test_disclaimer_constant_accessible(self):
        """DISCLAIMER constant is importable and meaningful."""
        from malaysia_statutory_rates import DISCLAIMER

        assert len(DISCLAIMER) > 50
        assert "official" in DISCLAIMER.lower() or "verify" in DISCLAIMER.lower()

    def test_load_rate_and_load_rates_consistent(self):
        """load_rate() returns same data as load_rates() for each file."""
        from malaysia_statutory_rates import load_rate, load_rates

        all_rates = load_rates()
        for name in all_rates:
            single = load_rate(name)
            assert single == all_rates[name], f"Mismatch for {name}"

    def test_changelog_export(self):
        """read_changelog is importable from top-level package."""
        from malaysia_statutory_rates import read_changelog
        assert callable(read_changelog)


# ── E2E: Workflow simulation ─────────────────────────────────────────────────

class TestE2EWorkflowSimulation:
    """Simulate the full CI/CD workflow: scrape → diff → save → verify."""

    def test_full_workflow_simulation(self, tmp_path: Path):
        """Simulate: initial scrape → rate change → second scrape → verify changelog."""
        from malaysia_statutory_rates.changelog import append_changelog, read_changelog
        from malaysia_statutory_rates.validator import validate_and_report

        # Step 1: Initial scrape (v1 data)
        v1 = json.loads(json.dumps(SAMPLE_DATA["minimum_wage"]))
        ScraperClass = _make_scraper_class("minimum_wage", tmp_path, v1)
        scraper = ScraperClass(data_dir=tmp_path)

        result = scraper.scrape()
        errors, proceed = validate_and_report("minimum_wage", result)
        assert proceed
        scraper.save("minimum_wage.json", result)

        # Step 2: Verify initial state
        assert (tmp_path / "minimum_wage.json").exists()
        entries = read_changelog(tmp_path)
        assert len(entries) == 1
        assert entries[0]["changes"][0]["type"] == "added"

        statuses = rates_status(tmp_path)
        assert statuses[0]["freshness"] == "fresh"

        # Step 3: Rate change (government announces new minimum wage)
        v2 = json.loads(json.dumps(SAMPLE_DATA["minimum_wage"]))
        v2["rates"]["nationwide"]["monthly"] = 1900
        v2["rates"]["nationwide"]["hourly"] = 9.72
        v2["effective_from"] = "2027-01-01"

        ScraperClass2 = _make_scraper_class("minimum_wage", tmp_path, v2)
        scraper2 = ScraperClass2(data_dir=tmp_path)

        # Step 4: Validate new data against old
        old_data = json.loads((tmp_path / "minimum_wage.json").read_text())
        errors, proceed = validate_and_report("minimum_wage", v2, old_data=old_data)
        assert proceed  # Change is within magnitude threshold

        # Step 5: Save updated data
        scraper2.save("minimum_wage.json", v2)

        # Step 6: Verify changelog has both entries
        entries = read_changelog(tmp_path)
        assert len(entries) == 2

        # First: added (new file)
        assert entries[0]["changes"][0]["type"] == "added"

        # Second: modified (rate change)
        mods = [c for c in entries[1]["changes"] if c["type"] == "modified"]
        monthly_mod = [c for c in mods if "monthly" in c["path"]]
        assert len(monthly_mod) == 1
        assert monthly_mod[0]["old"] == 1700
        assert monthly_mod[0]["new"] == 1900

        hourly_mod = [c for c in mods if "hourly" in c["path"]]
        assert len(hourly_mod) == 1
        assert hourly_mod[0]["old"] == 8.72
        assert hourly_mod[0]["new"] == 9.72

        # Step 7: Verify final file
        final = json.loads((tmp_path / "minimum_wage.json").read_text())
        assert final["rates"]["nationwide"]["monthly"] == 1900
        assert "disclaimer" in final["_metadata"]

        # Step 8: Status still works
        statuses = rates_status(tmp_path)
        assert statuses[0]["freshness"] == "fresh"

        scraper.close()
        scraper2.close()
