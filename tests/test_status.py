"""Tests for data freshness status."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from malaysia_statutory_rates.status import (
    format_status_table,
    rates_status,
)


def _make_rate_file(path: Path, source: str, scraped_at: str) -> None:
    """Create a minimal rate file with metadata."""
    data = {
        "source": source,
        "year": 2025,
        "_metadata": {
            "scraped_at": scraped_at,
            "source": source,
            "source_name": "test",
        },
    }
    path.write_text(json.dumps(data, indent=2) + "\n")


class TestRatesStatus:
    """Tests for rates_status()."""

    def test_empty_dir(self, tmp_path: Path):
        statuses = rates_status(tmp_path)
        assert statuses == []

    def test_fresh_file(self, tmp_path: Path):
        now = datetime.now(timezone.utc).isoformat()
        _make_rate_file(tmp_path / "epf_rates.json", "https://kwsp.gov.my", now)
        statuses = rates_status(tmp_path)
        assert len(statuses) == 1
        assert statuses[0]["freshness"] == "fresh"
        assert statuses[0]["age_days"] == 0

    def test_stale_file(self, tmp_path: Path):
        stale = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        _make_rate_file(tmp_path / "epf_rates.json", "https://kwsp.gov.my", stale)
        statuses = rates_status(tmp_path)
        assert statuses[0]["freshness"] == "stale"
        assert statuses[0]["age_days"] == 15

    def test_old_file(self, tmp_path: Path):
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        _make_rate_file(tmp_path / "epf_rates.json", "https://kwsp.gov.my", old)
        statuses = rates_status(tmp_path)
        assert statuses[0]["freshness"] == "old"
        assert statuses[0]["age_days"] == 60

    def test_missing_metadata(self, tmp_path: Path):
        data = {"source": "https://kwsp.gov.my", "year": 2025}
        (tmp_path / "epf_rates.json").write_text(json.dumps(data))
        statuses = rates_status(tmp_path)
        assert statuses[0]["freshness"] == "missing"

    def test_custom_thresholds(self, tmp_path: Path):
        three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        _make_rate_file(tmp_path / "test.json", "https://example.com", three_days_ago)

        # With fresh_days=1, 3 days ago should be stale
        statuses = rates_status(tmp_path, fresh_days=1)
        assert statuses[0]["freshness"] == "stale"

        # With fresh_days=5, 3 days ago should be fresh
        statuses = rates_status(tmp_path, fresh_days=5)
        assert statuses[0]["freshness"] == "fresh"

    def test_skips_changelog(self, tmp_path: Path):
        """_changelog.jsonl and files starting with _ should be skipped."""
        (tmp_path / "_changelog.jsonl").write_text('{"ts":"2025-01-01"}\n')
        _make_rate_file(tmp_path / "epf_rates.json", "https://kwsp.gov.my",
                        datetime.now(timezone.utc).isoformat())
        statuses = rates_status(tmp_path)
        assert len(statuses) == 1
        assert statuses[0]["name"] == "epf_rates"

    def test_multiple_files(self, tmp_path: Path):
        now = datetime.now(timezone.utc)
        _make_rate_file(tmp_path / "epf_rates.json", "https://kwsp.gov.my", now.isoformat())
        old = (now - timedelta(days=45)).isoformat()
        _make_rate_file(tmp_path / "socso_rates.json", "https://perkeso.gov.my", old)
        statuses = rates_status(tmp_path)
        assert len(statuses) == 2
        names = [s["name"] for s in statuses]
        assert "epf_rates" in names
        assert "socso_rates" in names


class TestFormatStatusTable:
    """Tests for format_status_table()."""

    def test_empty(self):
        result = format_status_table([])
        assert "No data files" in result

    def test_contains_all_fields(self):
        statuses = [{
            "name": "epf_rates",
            "source": "https://kwsp.gov.my/en/employer/responsibilities",
            "last_scraped": "2025-06-03",
            "age_days": 1,
            "freshness": "fresh",
        }]
        result = format_status_table(statuses)
        assert "epf_rates" in result
        assert "2025-06-03" in result
        assert "1d" in result
        assert "fresh" in result

    def test_truncates_long_source(self):
        statuses = [{
            "name": "test",
            "source": "https://example.com/very/long/path/that/goes/on/and/on/and/should/be/truncated",
            "last_scraped": "2025-06-03",
            "age_days": 0,
            "freshness": "fresh",
        }]
        result = format_status_table(statuses)
        assert "..." in result


class TestStatusWithRealData:
    """Test status against the actual bundled data files."""

    def test_all_files_have_status(self):
        statuses = rates_status()
        assert len(statuses) >= 8  # At least 8 rate files
        names = [s["name"] for s in statuses]
        assert "epf_rates" in names
        assert "minimum_wage" in names

    def test_all_files_report_freshness(self):
        statuses = rates_status()
        for s in statuses:
            assert s["freshness"] in ("fresh", "stale", "old", "missing", "error")
