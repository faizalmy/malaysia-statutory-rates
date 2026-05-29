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
    """Parse state text into list of individual state codes.

    Combined states like "Perlis & Terengganu" are split into
    individual entries: ["perlis", "terengganu"].
    """
    if not states_text:
        return []

    text = states_text.strip()
    if "national" in text.lower():
        return ["national"]

    # Split by comma and newlines first
    parts = re.split(r"[,\n]+", text)
    states = []
    for part in parts:
        part = part.strip().replace("<br>", "").strip()
        if not part:
            continue
        # Split combined states on & (e.g. "Perlis & Terengganu" -> ["Perlis", "Terengganu"])
        sub_parts = re.split(r"\s*&\s*", part)
        for sub in sub_parts:
            sub = sub.strip()
            if not sub:
                continue
            normalized = STATE_MAP.get(sub.lower(), sub.lower().replace(" ", "_"))
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

        # Extract year from page headings (e.g. "2026 Public Holidays")
        year = None
        for heading in soup.find_all(["h1", "h2", "h3"]):
            heading_text = heading.get_text(strip=True)
            year_match = re.search(r"(20\d{2})\s*(?:Public|Public Holiday)", heading_text)
            if year_match:
                year = int(year_match.group(1))
                break

        if year is None:
            # Fallback: find any 4-digit year in headings
            for heading in soup.find_all(["h1", "h2", "h3"]):
                year_match = re.search(r"\b(20\d{2})\b", heading.get_text())
                if year_match:
                    year = int(year_match.group(1))
                    break

        if year is None:
            raise ValueError("Could not determine holiday year from publicholidays.com.my")

        # Find the holidays table for the detected year
        tables = soup.find_all("table")
        target_table = None
        for table in tables:
            prev = table.find_previous(["h2", "h3"])
            if prev and str(year) in prev.get_text():
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
            raise ValueError(f"Could not find {year} holidays table on publicholidays.com.my")

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

            date_str = f"{year}-{month}-{day:02d}"
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
            "year": year,
            **holidays,
            "notes": self._extract_notes(soup),
        }

        if self.has_changed("public_holidays.json", data):
            return data
        return None

    def _extract_notes(self, soup: BeautifulSoup) -> list[str]:
        """Extract notes from page content."""
        notes = []
        full_text = soup.get_text()

        # Source attribution
        source_match = re.search(
            r"(based on[^.]*gazette[^.]*\.)", full_text, re.IGNORECASE
        )
        if source_match:
            notes.append(source_match.group(1).strip())

        # Islamic holidays caveat
        islamic_match = re.search(
            r"(Islamic holidays?[^.]*moon sighting[^.]*\.)", full_text, re.IGNORECASE
        )
        if islamic_match:
            notes.append(islamic_match.group(1).strip())
        else:
            # Look for any Islamic/moon sighting note
            islamic_match = re.search(
                r"(Hari Raya[^.]*\.)", full_text, re.IGNORECASE
            )
            if islamic_match:
                notes.append(islamic_match.group(1).strip())

        # State holidays note
        state_match = re.search(
            r"(State holidays?[^.]*state[^.]*\.)", full_text, re.IGNORECASE
        )
        if state_match:
            notes.append(state_match.group(1).strip())

        return notes
