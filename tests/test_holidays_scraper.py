"""Tests for HolidaysScraper and _parse_states."""

from unittest.mock import MagicMock

import pytest

from malaysia_statutory_rates.scrapers.holidays import HolidaysScraper, _parse_states


@pytest.fixture
def holidays_scraper(tmp_path):
    return HolidaysScraper(data_dir=tmp_path, respect_robots=False)


class TestParseStates:
    def test_national(self):
        assert _parse_states("National") == ["national"]

    def test_national_lowercase(self):
        assert _parse_states("national") == ["national"]

    def test_empty_string(self):
        assert _parse_states("") == []

    def test_single_state(self):
        assert _parse_states("Johor") == ["johor"]

    def test_multiple_states_comma(self):
        result = _parse_states("Kuala Lumpur, Putrajaya, Johor")
        assert "kuala_lumpur" in result
        assert "putrajaya" in result
        assert "johor" in result

    def test_combined_states_ampersand(self):
        result = _parse_states("Perlis & Terengganu")
        assert "perlis" in result
        assert "terengganu" in result

    def test_mixed_comma_and_ampersand(self):
        result = _parse_states("Kuala Lumpur, Perlis & Terengganu")
        assert "kuala_lumpur" in result
        assert "perlis" in result
        assert "terengganu" in result

    def test_state_normalization(self):
        assert _parse_states("Negeri Sembilan") == ["negeri_sembilan"]

    def test_unknown_state_lowercased(self):
        result = _parse_states("Some New State")
        assert "some_new_state" in result

    def test_br_tags_stripped(self):
        result = _parse_states("Johor,<br>Kedah")
        assert "johor" in result
        assert "kedah" in result

    def test_newline_split(self):
        result = _parse_states("Johor\nKedah")
        assert "johor" in result
        assert "kedah" in result

    def test_all_16_states(self):
        for state in ["johor", "kedah", "kelantan", "kuala_lumpur", "labuan",
                       "melaka", "negeri_sembilan", "pahang", "penang", "perak",
                       "perlis", "putrajaya", "sabah", "sarawak", "selangor", "terengganu"]:
            result = _parse_states(state.title().replace("_", " "))
            assert state in result


class TestHolidaysScrape:
    def test_scrape_success(self, holidays_scraper, holidays_html):
        holidays_scraper.fetch = MagicMock(return_value=holidays_html)
        holidays_scraper.has_changed = MagicMock(return_value=True)
        result = holidays_scraper.scrape()
        assert result is not None
        assert result["year"] == 2026
        assert len(result["national"]) > 0

    def test_scrape_unchanged_returns_none(self, holidays_scraper, holidays_html):
        holidays_scraper.fetch = MagicMock(return_value=holidays_html)
        holidays_scraper.has_changed = MagicMock(return_value=False)
        result = holidays_scraper.scrape()
        assert result is None

    def test_scrape_no_year_raises(self, holidays_scraper):
        html = "<html><body><table><tr><td>1 Jan</td><td>Mon</td><td>Holiday</td><td>National</td></tr></table></body></html>"
        holidays_scraper.fetch = MagicMock(return_value=html)
        with pytest.raises(ValueError, match="Could not determine holiday year"):
            holidays_scraper.scrape()

    def test_scrape_no_table_raises(self, holidays_scraper):
        html = "<html><body><h2>2026 Public Holidays</h2></body></html>"
        holidays_scraper.fetch = MagicMock(return_value=html)
        with pytest.raises(ValueError, match="Could not find"):
            holidays_scraper.scrape()

    def test_scrape_national_holidays(self, holidays_scraper, holidays_html):
        holidays_scraper.fetch = MagicMock(return_value=holidays_html)
        holidays_scraper.has_changed = MagicMock(return_value=True)
        result = holidays_scraper.scrape()
        national_names = [h["name"] for h in result["national"]]
        assert len(national_names) >= 2  # New Year + CNY

    def test_scrape_state_holidays(self, holidays_scraper, holidays_html):
        holidays_scraper.fetch = MagicMock(return_value=holidays_html)
        holidays_scraper.has_changed = MagicMock(return_value=True)
        result = holidays_scraper.scrape()
        assert "johor" in result["state"]
        # Federal Territory Day should have kuala_lumpur as state
        assert "kuala_lumpur" in result["state"]

    def test_scrape_date_format(self, holidays_scraper, holidays_html):
        holidays_scraper.fetch = MagicMock(return_value=holidays_html)
        holidays_scraper.has_changed = MagicMock(return_value=True)
        result = holidays_scraper.scrape()
        for h in result["national"]:
            assert h["date"].startswith("2026-")

    def test_scrape_unknown_month_skipped(self, holidays_scraper):
        html = """
        <html><body>
        <h2>2026 Public Holidays</h2>
        <table>
          <tr><th>Date</th><th>Day</th><th>Holiday</th><th>States</th></tr>
          <tr><td>1 Xxx</td><td>Mon</td><td>Fake Holiday</td><td>National</td></tr>
          <tr><td>1 Jan</td><td>Wed</td><td>New Year</td><td>National</td></tr>
        </table>
        </body></html>
        """
        holidays_scraper.fetch = MagicMock(return_value=html)
        holidays_scraper.has_changed = MagicMock(return_value=True)
        result = holidays_scraper.scrape()
        assert len(result["national"]) == 1

    def test_scrape_fallback_heading_year(self, holidays_scraper):
        html = """
        <html><body>
        <h3>2026</h3>
        <table>
          <tr><th>Date</th><th>Day</th><th>Holiday</th><th>States</th></tr>
          <tr><td>1 Jan</td><td>Wed</td><td>New Year</td><td>National</td></tr>
        </table>
        </body></html>
        """
        holidays_scraper.fetch = MagicMock(return_value=html)
        holidays_scraper.has_changed = MagicMock(return_value=True)
        result = holidays_scraper.scrape()
        assert result["year"] == 2026

    def test_scrape_fallback_first_large_table(self, holidays_scraper):
        rows = "\n".join([
            f'<tr><td>{i} Jan</td><td>Mon</td><td>Holiday {i}</td><td>National</td></tr>'
            for i in range(1, 15)
        ])
        html = f"""
        <html><body>
        <h1>2026 Holidays</h1>
        <table>{rows}</table>
        </body></html>
        """
        holidays_scraper.fetch = MagicMock(return_value=html)
        holidays_scraper.has_changed = MagicMock(return_value=True)
        result = holidays_scraper.scrape()
        assert len(result["national"]) == 14

    def test_scrape_empty_date_skipped(self, holidays_scraper):
        html = """
        <html><body>
        <h2>2026 Public Holidays</h2>
        <table>
          <tr><th>Date</th><th>Day</th><th>Holiday</th><th>States</th></tr>
          <tr><td></td><td></td><td></td><td></td></tr>
          <tr><td>1 Jan</td><td>Wed</td><td>New Year</td><td>National</td></tr>
        </table>
        </body></html>
        """
        holidays_scraper.fetch = MagicMock(return_value=html)
        holidays_scraper.has_changed = MagicMock(return_value=True)
        result = holidays_scraper.scrape()
        assert len(result["national"]) == 1
