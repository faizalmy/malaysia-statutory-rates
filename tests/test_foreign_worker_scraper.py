"""Tests for ForeignWorkerScraper."""

from unittest.mock import MagicMock, patch

import pytest

from malaysia_statutory_rates.scrapers.foreign_worker import ForeignWorkerScraper


@pytest.fixture
def fw_scraper(tmp_path):
    return ForeignWorkerScraper(data_dir=tmp_path, respect_robots=False)


SAMPLE_EPF = {
    "source": "https://www.kwsp.gov.my/test",
    "year": 2025,
    "effective_from": "2025-10-01",
    "rates": {
        "non_malaysian_after_aug98": {
            "employee": {"rate": 0.0},
            "employer": {"rate": 0.02},
            "note": "Non-Malaysian registered from 1 August 1998",
        },
        "malaysian_pr_nonmy_before_aug98_below_60": {
            "employee": {"rate": 0.11},
            "employer": {"wage_lte_5000": {"rate": 0.13}},
        },
        "pr_nonmy_before_aug98_60_plus": {
            "employee": {"rate": 0.0},
            "employer": {"rate": 0.04},
        },
    },
}

SAMPLE_SOCSO = {
    "source": "https://www.perkeso.gov.my/test",
    "wage_ceiling": 6000,
    "schemes": {
        "employment_injury": {"employer_only": True},
    },
    "rate_table": [
        {"row": 1, "wage_min": 0, "wage_max": 30, "employer_schedule1": 0.4},
        {"row": 65, "wage_min": 5900, "wage_max": 6000, "employer_schedule1": 107.15},
    ],
}

SAMPLE_EIS = {
    "source": "https://www.perkeso.gov.my/test",
    "wage_ceiling": 6000,
    "rate_table": [
        {"row": 1, "wage_min": 0, "wage_max": 30, "employer": 0.05, "employee": 0.05, "total": 0.1},
        {"row": 65, "wage_min": 5900, "wage_max": 6000, "employer": 11.1, "employee": 11.1, "total": 22.2},
    ],
}


class TestForeignWorkerScrape:
    @patch("malaysia_statutory_rates.loader.load_rates")
    def test_scrape_success(self, mock_load, fw_scraper):
        mock_load.return_value = {
            "epf_rates": SAMPLE_EPF,
            "socso_rates": SAMPLE_SOCSO,
            "eis_rates": SAMPLE_EIS,
        }
        fw_scraper.has_changed = MagicMock(return_value=True)
        result = fw_scraper.scrape()
        assert result is not None
        assert result["year"] == 2025
        assert result["effective_from"] == "2025-10-01"
        assert "epf" in result
        assert "socso" in result
        assert "eis" in result

    @patch("malaysia_statutory_rates.loader.load_rates")
    def test_scrape_unchanged_returns_none(self, mock_load, fw_scraper):
        mock_load.return_value = {
            "epf_rates": SAMPLE_EPF,
            "socso_rates": SAMPLE_SOCSO,
            "eis_rates": SAMPLE_EIS,
        }
        fw_scraper.has_changed = MagicMock(return_value=False)
        result = fw_scraper.scrape()
        assert result is None

    @patch("malaysia_statutory_rates.loader.load_rates")
    def test_scrape_no_epf_returns_none(self, mock_load, fw_scraper):
        mock_load.return_value = {}
        result = fw_scraper.scrape()
        assert result is None

    @patch("malaysia_statutory_rates.loader.load_rates")
    def test_scrape_extracts_epf_non_my_after_aug98(self, mock_load, fw_scraper):
        mock_load.return_value = {
            "epf_rates": SAMPLE_EPF,
            "socso_rates": SAMPLE_SOCSO,
            "eis_rates": SAMPLE_EIS,
        }
        fw_scraper.has_changed = MagicMock(return_value=True)
        result = fw_scraper.scrape()
        epf = result["epf"]["non_malaysian_after_aug98"]
        assert epf["employee"]["rate"] == 0.0
        assert epf["employer"]["rate"] == 0.02

    @patch("malaysia_statutory_rates.loader.load_rates")
    def test_scrape_extracts_socso_employment_injury(self, mock_load, fw_scraper):
        mock_load.return_value = {
            "epf_rates": SAMPLE_EPF,
            "socso_rates": SAMPLE_SOCSO,
            "eis_rates": SAMPLE_EIS,
        }
        fw_scraper.has_changed = MagicMock(return_value=True)
        result = fw_scraper.scrape()
        socso = result["socso"]["employment_injury"]
        assert socso["employer_only"] is True
        assert socso["wage_ceiling"] == 6000

    @patch("malaysia_statutory_rates.loader.load_rates")
    def test_scrape_extracts_eis_data(self, mock_load, fw_scraper):
        mock_load.return_value = {
            "epf_rates": SAMPLE_EPF,
            "socso_rates": SAMPLE_SOCSO,
            "eis_rates": SAMPLE_EIS,
        }
        fw_scraper.has_changed = MagicMock(return_value=True)
        result = fw_scraper.scrape()
        eis = result["eis"]
        assert eis["wage_ceiling"] == 6000
        assert eis["contribution_at_ceiling"]["total"] == 22.2

    @patch("malaysia_statutory_rates.loader.load_rates")
    def test_scrape_no_rate_table(self, mock_load, fw_scraper):
        epf_no_table = {**SAMPLE_EPF}
        socso_no_table = {"wage_ceiling": 6000, "schemes": {"employment_injury": {"employer_only": True}}}
        eis_no_table = {"wage_ceiling": 6000}
        mock_load.return_value = {
            "epf_rates": epf_no_table,
            "socso_rates": socso_no_table,
            "eis_rates": eis_no_table,
        }
        fw_scraper.has_changed = MagicMock(return_value=True)
        result = fw_scraper.scrape()
        assert result is not None

    @patch("malaysia_statutory_rates.loader.load_rates")
    def test_scrape_socso_invalidity_note(self, mock_load, fw_scraper):
        mock_load.return_value = {
            "epf_rates": SAMPLE_EPF,
            "socso_rates": SAMPLE_SOCSO,
            "eis_rates": SAMPLE_EIS,
        }
        fw_scraper.has_changed = MagicMock(return_value=True)
        result = fw_scraper.scrape()
        assert result["socso"]["invalidity"] is not None  # has invalidity structure

    @patch("malaysia_statutory_rates.loader.load_rates")
    def test_scrape_notes(self, mock_load, fw_scraper):
        mock_load.return_value = {
            "epf_rates": SAMPLE_EPF,
            "socso_rates": SAMPLE_SOCSO,
            "eis_rates": SAMPLE_EIS,
        }
        fw_scraper.has_changed = MagicMock(return_value=True)
        result = fw_scraper.scrape()
        assert len(result["notes"]) >= 1
