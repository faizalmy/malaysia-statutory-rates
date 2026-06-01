"""Tests for the scrapers __init__ module (SCRAPERS dict, run_scrapers)."""

from unittest.mock import MagicMock, patch

from malaysia_statutory_rates.scrapers import SCRAPERS, run_scrapers


class TestScrapersDict:
    def test_scrapers_has_all_entries(self):
        expected = {
            "minimum_wage", "hrdf_rates", "epf_rates", "socso_rates",
            "eis_rates", "pcb_table", "foreign_worker_rates", "public_holidays",
        }
        assert set(SCRAPERS.keys()) == expected

    def test_scrapers_all_have_scrape_method(self):
        for name, cls in SCRAPERS.items():
            assert hasattr(cls, "scrape"), f"{name} missing scrape()"

    def test_scrapers_all_have_save_method(self):
        for name, cls in SCRAPERS.items():
            assert hasattr(cls, "save"), f"{name} missing save()"


class TestRunScrapers:
    @patch("malaysia_statutory_rates.scrapers.SCRAPERS")
    def test_run_scrapers_success_changed(self, mock_scrapers):
        scraper = MagicMock()
        scraper.scrape.return_value = {"key": "value"}
        mock_cls = MagicMock(return_value=scraper)
        mock_scrapers.__iter__ = MagicMock(return_value=iter(["test_scraper"]))
        mock_scrapers.__getitem__ = MagicMock(return_value=mock_cls)
        mock_scrapers.keys.return_value = ["test_scraper"]
        mock_scrapers.__contains__ = MagicMock(side_effect=lambda x: x == "test_scraper")

        results = run_scrapers(["test_scraper"])
        assert results["test_scraper"] is True
        scraper.save.assert_called_once_with("test_scraper.json", {"key": "value"})

    @patch("malaysia_statutory_rates.scrapers.SCRAPERS")
    def test_run_scrapers_unchanged(self, mock_scrapers):
        scraper = MagicMock()
        scraper.scrape.return_value = None
        mock_cls = MagicMock(return_value=scraper)
        mock_scrapers.__iter__ = MagicMock(return_value=iter(["test_scraper"]))
        mock_scrapers.__getitem__ = MagicMock(return_value=mock_cls)
        mock_scrapers.keys.return_value = ["test_scraper"]
        mock_scrapers.__contains__ = MagicMock(side_effect=lambda x: x == "test_scraper")

        results = run_scrapers(["test_scraper"])
        assert results["test_scraper"] is False
        scraper.save.assert_not_called()

    @patch("malaysia_statutory_rates.scrapers.SCRAPERS")
    def test_run_scrapers_unknown_skipped(self, mock_scrapers, capsys):
        mock_scrapers.__contains__ = MagicMock(return_value=False)
        mock_scrapers.keys.return_value = []

        results = run_scrapers(["unknown_scraper"])
        assert results == {}
        out = capsys.readouterr().out
        assert "WARNING" in out

    @patch("malaysia_statutory_rates.scrapers.SCRAPERS")
    def test_run_scrapers_exception_returns_false(self, mock_scrapers, capsys):
        scraper = MagicMock()
        scraper.scrape.side_effect = ValueError("parse error")
        mock_cls = MagicMock(return_value=scraper)
        mock_scrapers.__iter__ = MagicMock(return_value=iter(["test_scraper"]))
        mock_scrapers.__getitem__ = MagicMock(return_value=mock_cls)
        mock_scrapers.keys.return_value = ["test_scraper"]
        mock_scrapers.__contains__ = MagicMock(side_effect=lambda x: x == "test_scraper")

        results = run_scrapers(["test_scraper"])
        assert results["test_scraper"] is False
        out = capsys.readouterr().out
        assert "ERROR" in out

    @patch("malaysia_statutory_rates.scrapers.SCRAPERS")
    def test_run_scrapers_none_targets_runs_all(self, mock_scrapers):
        scraper = MagicMock()
        scraper.scrape.return_value = None
        mock_cls = MagicMock(return_value=scraper)
        mock_scrapers.__iter__ = MagicMock(return_value=iter(["s1", "s2"]))
        mock_scrapers.__getitem__ = MagicMock(return_value=mock_cls)
        mock_scrapers.keys.return_value = ["s1", "s2"]
        mock_scrapers.__contains__ = MagicMock(side_effect=lambda x: x in ["s1", "s2"])

        results = run_scrapers(None)
        assert len(results) == 2
