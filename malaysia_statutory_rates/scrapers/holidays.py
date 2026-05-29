"""Scrape Malaysian public holidays from publicholidays.com.my."""

import re

from bs4 import BeautifulSoup

from malaysia_statutory_rates.scrapers.base import BaseScraper

# State name normalization
STATE_MAP = {
    "johor": "johor",
    "kedah": "kedah",
    "kelantan": "kelantan",
    "kuala lumpur": "kuala_lumpur",
    "labuan": "labuan",
    "melaka": "melaka",
    "negeri sembilan": "negeri_sembilan",
    "pahang": "pahang",
    "penang": "penang",
    "perak": "perak",
    "perlis": "perlis",
    "putrajaya": "putrajaya",
    "sabah": "sabah",
    "sarawak": "sarawak",
    "selangor": "selangor",
    "terengganu": "terengganu",
}


def _parse_states(states_text: str) -> list[str]:
    """Parse state text into list of state codes."""
    if not states_text:
        return []

    text = states_text.strip()
    if "national" in text.lower():
        states = ["national"]
        # Check for exceptions
        except_match = re.search(r"except\s+(.+?)(?:\s*$)", text, re.IGNORECASE)
        if except_match:
            # Parse exceptions but keep them in the states list with "except_" prefix
            pass
        return states

    # Split by comma and newlines
    parts = re.split(r"[,\n]+", text)
    states = []
    for part in parts:
        part = part.strip().replace("<br>", "").strip()
        if not part:
            continue
        normalized = STATE_MAP.get(part.lower(), part.lower().replace(" ", "_"))
        states.append(normalized)
    return states


class HolidaysScraper(BaseScraper):
    """Scrape public holidays from publicholidays.com.my."""

    SOURCE_URL = "https://publicholidays.com.my/"
    SOURCE_NAME = "PublicHolidays.com.my (based on government gazette)"

    def scrape(self) -> dict | None:
        html = self.fetch(self.SOURCE_URL)
        soup = BeautifulSoup(html, "html.parser")

        holidays = {"national": [], "state": {}}

        # Find the 2026 table
        tables = soup.find_all("table")
        target_table = None
        for table in tables:
            # Look for table preceded by "2026 Public Holidays" heading
            prev = table.find_previous(["h2", "h3"])
            if prev and "2026" in prev.get_text():
                target_table = table
                break

        if not target_table:
            # Fallback: use first table with holiday-like content
            for table in tables:
                rows = table.find_all("tr")
                if len(rows) > 10:  # Likely the main holidays table
                    target_table = table
                    break

        if not target_table:
            raise ValueError("Could not find 2026 holidays table on publicholidays.com.my")

        for row in target_table.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) < 3:
                continue

            date_text = cols[0].get_text(strip=True)
            # Skip empty rows
            if not date_text:
                continue

            holiday_name = cols[2].get_text(strip=True)
            states_text = cols[3].get_text(strip=True) if len(cols) > 3 else ""

            # Parse date (format: "1 Jan", "14 Jan", etc.)
            date_match = re.match(r"(\d{1,2})\s+(\w+)", date_text)
            if not date_match:
                continue

            day = int(date_match.group(1))
            month_name = date_match.group(2)

            # Convert month name to number
            months = {
                "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
                "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
                "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
            }
            month = months.get(month_name)
            if not month:
                continue

            date_str = f"2026-{month}-{day:02d}"
            states = _parse_states(states_text)

            entry = {
                "date": date_str,
                "name": holiday_name,
                "states": states,
            }

            if "national" in states:
                holidays["national"].append(entry)
            else:
                for state in states:
                    if state not in holidays["state"]:
                        holidays["state"][state] = []
                    holidays["state"][state].append(entry)

        data = {
            "source": self.SOURCE_URL,
            "year": 2026,
            "gazette_source": "https://www.kabinet.gov.my/storage/2025/08/HKA-2026.pdf",
            **holidays,
            "notes": [
                "Data from publicholidays.com.my, based on official government gazette",
                "Islamic holidays (Hari Raya, etc.) are approximate — actual dates depend on moon sighting",
                "State holidays are only observed in the respective state",
            ],
        }

        if self.has_changed("public_holidays.json", data):
            return data
        return None
