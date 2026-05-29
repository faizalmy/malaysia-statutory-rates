"""Tests for data file schema validation."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

REQUIRED_METADATA = ["scraped_at", "source", "source_name", "scraper_version"]


def test_all_data_files_have_metadata():
    """Every JSON file in data/ must have _metadata."""
    for json_file in sorted(DATA_DIR.glob("*.json")):
        data = json.loads(json_file.read_text())
        assert "_metadata" in data, f"{json_file.name} missing _metadata"
        for field in REQUIRED_METADATA:
            assert field in data["_metadata"], (
                f"{json_file.name} _metadata missing '{field}'"
            )


def test_all_data_files_have_source():
    """Every JSON file must have a source URL."""
    for json_file in sorted(DATA_DIR.glob("*.json")):
        data = json.loads(json_file.read_text())
        assert "source" in data, f"{json_file.name} missing 'source'"


def test_no_empty_data_files():
    """No JSON file should be empty or just metadata."""
    for json_file in sorted(DATA_DIR.glob("*.json")):
        data = json.loads(json_file.read_text())
        # Remove metadata, should have at least one real key
        real_keys = {k for k in data if k != "_metadata"}
        assert len(real_keys) >= 1, f"{json_file.name} has no data beyond _metadata"
