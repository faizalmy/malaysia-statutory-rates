"""Tests for disclaimer in data files and Python package."""

import json
from pathlib import Path

from malaysia_statutory_rates import DISCLAIMER


class TestDisclaimerConstant:
    """Tests for the DISCLAIMER constant."""

    def test_disclaimer_exists(self):
        assert DISCLAIMER is not None
        assert isinstance(DISCLAIMER, str)

    def test_disclaimer_mentions_verify(self):
        assert "verify" in DISCLAIMER.lower()

    def test_disclaimer_mentions_risk(self):
        assert "risk" in DISCLAIMER.lower()

    def test_disclaimer_mentions_github(self):
        assert "github.com" in DISCLAIMER


class TestDisclaimerInDataFiles:
    """Tests that data files disclaimer metadata is available."""

    def test_disclaimer_schema_compatible(self):
        """Disclaimer fields should be strings when present."""
        data_dir = Path(__file__).parent.parent / "malaysia_statutory_rates" / "data"
        for json_file in sorted(data_dir.glob("*.json")):
            if json_file.name.startswith("_"):
                continue
            data = json.loads(json_file.read_text())
            metadata = data.get("_metadata", {})
            if "disclaimer" in metadata:
                assert isinstance(metadata["disclaimer"], str)


class TestDisclaimerInNewSaves:
    """Test that new saves include disclaimer metadata."""

    def test_save_includes_disclaimer(self, tmp_path: Path):
        from malaysia_statutory_rates.scrapers.base import BaseScraper

        class TestScraper(BaseScraper):
            SOURCE_URL = "https://example.com"
            SOURCE_NAME = "Test Source"

            def scrape(self):
                return None

        scraper = TestScraper(data_dir=tmp_path)
        scraper.save("test.json", {"rates": {"employer": 0.13}})
        data = json.loads((tmp_path / "test.json").read_text())
        assert "disclaimer" in data["_metadata"]
        assert "verify" in data["_metadata"]["disclaimer"].lower()
        assert data["_metadata"]["official_reference"] == "Test Source"
