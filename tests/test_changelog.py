"""Tests for the audit changelog system."""

import json
from pathlib import Path

from malaysia_statutory_rates.changelog import (
    append_changelog,
    diff_changes,
    read_changelog,
)


class TestDiffChanges:
    """Tests for diff_changes() utility."""

    def test_no_changes(self):
        old = {"a": 1, "b": 2}
        new = {"a": 1, "b": 2}
        assert diff_changes(old, new) == []

    def test_modified_scalar(self):
        old = {"rate": 0.13}
        new = {"rate": 0.12}
        changes = diff_changes(old, new)
        assert len(changes) == 1
        assert changes[0]["type"] == "modified"
        assert changes[0]["path"] == "rate"
        assert changes[0]["old"] == 0.13
        assert changes[0]["new"] == 0.12

    def test_added_key(self):
        old = {"a": 1}
        new = {"a": 1, "b": 2}
        changes = diff_changes(old, new)
        assert len(changes) == 1
        assert changes[0]["type"] == "added"
        assert changes[0]["path"] == "b"
        assert changes[0]["new"] == 2

    def test_removed_key(self):
        old = {"a": 1, "b": 2}
        new = {"a": 1}
        changes = diff_changes(old, new)
        assert len(changes) == 1
        assert changes[0]["type"] == "removed"
        assert changes[0]["path"] == "b"
        assert changes[0]["old"] == 2

    def test_nested_changes(self):
        old = {"rates": {"employer": {"rate": 0.13}}}
        new = {"rates": {"employer": {"rate": 0.12}}}
        changes = diff_changes(old, new)
        assert len(changes) == 1
        assert changes[0]["path"] == "rates.employer.rate"
        assert changes[0]["old"] == 0.13
        assert changes[0]["new"] == 0.12

    def test_multiple_changes(self):
        old = {"a": 1, "b": 2, "c": 3}
        new = {"a": 1, "b": 99, "d": 4}
        changes = diff_changes(old, new)
        assert len(changes) == 3
        types = {c["path"]: c["type"] for c in changes}
        assert types["b"] == "modified"
        assert types["c"] == "removed"
        assert types["d"] == "added"

    def test_list_of_dicts_with_identity_key(self):
        """Lists of dicts should diff by identity key (e.g. 'name')."""
        old = {"holidays": [{"name": "New Year", "date": "2025-01-01"}]}
        new = {"holidays": [
            {"name": "New Year", "date": "2025-01-02"},  # date changed
            {"name": "Labour Day", "date": "2025-05-01"},  # added
        ]}
        changes = diff_changes(old, new)
        # Should detect date change for New Year and addition of Labour Day
        assert len(changes) >= 2
        paths = [c["path"] for c in changes]
        assert any("New Year" in p for p in paths)
        assert any("Labour Day" in p for p in paths)

    def test_list_index_fallback(self):
        """Lists of scalars should diff by index."""
        old = {"tags": ["a", "b", "c"]}
        new = {"tags": ["a", "x", "c", "d"]}
        changes = diff_changes(old, new)
        assert len(changes) == 2  # modified [1], added [3]

    def test_empty_dicts(self):
        assert diff_changes({}, {}) == []

    def test_from_empty(self):
        changes = diff_changes({}, {"a": 1})
        assert len(changes) == 1
        assert changes[0]["type"] == "added"


class TestAppendChangelog:
    """Tests for append_changelog()."""

    def test_creates_changelog_file(self, tmp_path: Path):
        new_data = {"rates": {"employer": 0.12}, "_metadata": {"scraped_at": "2025-01-01"}}
        append_changelog(tmp_path, "epf_rates", "https://kwsp.gov.my", None, new_data)

        changelog = tmp_path / "_changelog.jsonl"
        assert changelog.exists()
        entries = [json.loads(line) for line in changelog.read_text().strip().split("\n")]
        assert len(entries) == 1
        assert entries[0]["scraper"] == "epf_rates"
        assert entries[0]["change_count"] == 1
        assert entries[0]["changes"][0]["type"] == "added"

    def test_appends_multiple_entries(self, tmp_path: Path):
        data1 = {"rates": {"employer": 0.13}}
        data2 = {"rates": {"employer": 0.12}}
        data3 = {"rates": {"employer": 0.11}}

        append_changelog(tmp_path, "epf_rates", "https://kwsp.gov.my", None, data1)
        append_changelog(tmp_path, "epf_rates", "https://kwsp.gov.my", data1, data2)
        append_changelog(tmp_path, "epf_rates", "https://kwsp.gov.my", data2, data3)

        entries = read_changelog(tmp_path)
        assert len(entries) == 3
        assert entries[0]["changes"][0]["type"] == "added"
        assert entries[1]["changes"][0]["old"] == 0.13
        assert entries[1]["changes"][0]["new"] == 0.12
        assert entries[2]["changes"][0]["old"] == 0.12
        assert entries[2]["changes"][0]["new"] == 0.11

    def test_strips_metadata_from_diff(self, tmp_path: Path):
        old = {"rates": {"employer": 0.13}, "_metadata": {"scraped_at": "2025-01-01"}}
        new = {"rates": {"employer": 0.13}, "_metadata": {"scraped_at": "2025-06-01"}}
        append_changelog(tmp_path, "epf_rates", "https://kwsp.gov.my", old, new)

        entries = read_changelog(tmp_path)
        # Should have 0 changes since only _metadata differed
        assert entries[0]["change_count"] == 0

    def test_hash_chain(self, tmp_path: Path):
        data1 = {"a": 1}
        data2 = {"a": 2}
        append_changelog(tmp_path, "test", "https://example.com", None, data1)
        append_changelog(tmp_path, "test", "https://example.com", data1, data2)

        entries = read_changelog(tmp_path)
        assert entries[0]["prev_hash"] is None
        assert entries[0]["new_hash"] is not None
        assert entries[1]["prev_hash"] == entries[0]["new_hash"]


class TestReadChangelog:
    """Tests for read_changelog()."""

    def test_empty_changelog(self, tmp_path: Path):
        assert read_changelog(tmp_path) == []

    def test_last_n(self, tmp_path: Path):
        for i in range(10):
            data = {"value": i}
            prev = {"value": i - 1} if i > 0 else None
            append_changelog(tmp_path, "test", "https://example.com", prev, data)

        entries = read_changelog(tmp_path, last_n=3)
        assert len(entries) == 3
        assert entries[0]["changes"][0]["new"] == 7 or entries[0]["changes"][0]["type"] == "modified"
