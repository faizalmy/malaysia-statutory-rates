"""Tests for the CLI module."""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestRateMap:
    def test_rate_map_keys(self):
        from malaysia_statutory_rates.cli import RATE_MAP
        expected = {"epf", "socso", "eis", "pcb", "minimum-wage", "hrdf", "holidays", "foreign-workers"}
        assert set(RATE_MAP.keys()) == expected

    def test_rate_map_values_are_filenames(self):
        from malaysia_statutory_rates.cli import RATE_MAP
        for name in RATE_MAP.values():
            assert name.isidentifier() or "_" in name


class TestCmdShow:
    def test_cmd_show_all(self, capsys):
        from malaysia_statutory_rates.cli import cmd_show
        args = MagicMock()
        args.rate = "all"
        with patch("malaysia_statutory_rates.cli.load_rates") as mock_load:
            mock_load.return_value = {"epf_rates": {"key": "value"}}
            cmd_show(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "epf_rates" in data

    def test_cmd_show_single_rate(self, capsys):
        from malaysia_statutory_rates.cli import cmd_show
        args = MagicMock()
        args.rate = "epf"
        with patch("malaysia_statutory_rates.cli.load_rate") as mock_load:
            mock_load.return_value = {"year": 2025}
            cmd_show(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "epf" in data
        assert data["epf"]["year"] == 2025

    def test_cmd_show_unknown_rate_uses_as_filename(self, capsys):
        from malaysia_statutory_rates.cli import cmd_show
        args = MagicMock()
        args.rate = "custom_rate"
        with patch("malaysia_statutory_rates.cli.load_rate") as mock_load:
            mock_load.return_value = {"custom": True}
            cmd_show(args)
        mock_load.assert_called_once_with("custom_rate")


class TestCmdScrape:
    def test_cmd_scrape_all(self, capsys):
        from malaysia_statutory_rates.cli import cmd_scrape
        args = MagicMock()
        args.all = True
        args.targets = []
        args.strict = False
        with patch("malaysia_statutory_rates.scrapers.run_scrapers") as mock_run:
            mock_run.return_value = {"epf_rates": True, "socso_rates": False}
            cmd_scrape(args)
        out = capsys.readouterr().out
        assert "UPDATED" in out
        assert "unchanged" in out
        mock_run.assert_called_once_with(None, strict=False)

    def test_cmd_scrape_targets(self, capsys):
        from malaysia_statutory_rates.cli import cmd_scrape
        args = MagicMock()
        args.all = False
        args.targets = ["epf_rates"]
        args.strict = False
        with patch("malaysia_statutory_rates.scrapers.run_scrapers") as mock_run:
            mock_run.return_value = {"epf_rates": True}
            cmd_scrape(args)
        mock_run.assert_called_once_with(["epf_rates"], strict=False)

    def test_cmd_scrape_no_targets_exits(self):
        from malaysia_statutory_rates.cli import cmd_scrape
        args = MagicMock()
        args.all = False
        args.targets = []
        with pytest.raises(SystemExit) as exc_info:
            cmd_scrape(args)
        assert exc_info.value.code == 1


class TestMain:
    def test_main_show_command(self, capsys):
        test_args = ["prog", "show", "all"]
        with patch("sys.argv", test_args):
            with patch("malaysia_statutory_rates.cli.load_rates") as mock_load:
                mock_load.return_value = {"test": {}}
                from malaysia_statutory_rates.cli import main
                main()
        out = capsys.readouterr().out
        assert "test" in out

    def test_main_no_command_exits(self):
        test_args = ["prog"]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                from malaysia_statutory_rates.cli import main
                main()
            assert exc_info.value.code == 1

    def test_main_help(self, capsys):
        test_args = ["prog", "--help"]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                from malaysia_statutory_rates.cli import main
                main()
            assert exc_info.value.code == 0
