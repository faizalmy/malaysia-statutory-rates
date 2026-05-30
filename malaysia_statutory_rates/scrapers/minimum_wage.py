"""Scrape minimum wage data from MOHR portal."""

import re

from bs4 import BeautifulSoup

from malaysia_statutory_rates.scrapers.base import BaseScraper


class MinimumWageScraper(BaseScraper):
    """Scrape minimum wage from gajiminimum.mohr.gov.my."""

    SOURCE_URL = "https://gajiminimum.mohr.gov.my/"
    SOURCE_NAME = "Sekretariat Majlis Perundingan Gaji Negara (MPGN)"

    def scrape(self) -> dict | None:
        html = self.fetch(self.SOURCE_URL)
        soup = BeautifulSoup(html, "html.parser")

        # Strategy 1: Find specific HTML elements
        # The page has <h2>1700</h2> and <div>RM8.72</div> in a structured layout
        # Also has <h5>Kadar Gaji MinimumBulanan</h5> as labels
        monthly = None
        hourly = None
        gazette_link = None

        # Find all h2, h5, div elements and look for the rate pattern
        # Monthly: <div> contains "RM1700" then <h2> has "1700"
        # Hourly: <div> contains "RM8.72"
        for div in soup.find_all("div"):
            text = div.get_text(strip=True)
            # Monthly rate: div contains "RM" + digits + "Kadar Gaji Minimum"
            m = re.match(r"^RM(\d[\d,]*)Kadar Gaji Minimum", text)
            if m:
                monthly = int(m.group(1).replace(",", ""))
                continue
            # Hourly rate: div contains "RM" + decimal + "Kadar Gaji Minimum"
            h = re.match(r"^RM([\d.]+)Kadar Gaji Minimum", text)
            if h:
                hourly = float(h.group(1))
                continue
            # Standalone div with just the number
            if re.match(r"^RM(\d[\d,]*)$", text):
                val = int(text.replace("RM", "").replace(",", ""))
                if val > 100:  # monthly
                    monthly = val
                continue
            if re.match(r"^RM[\d.]+$", text):
                val = float(text.replace("RM", ""))
                if val < 100:  # hourly
                    hourly = val
                    continue

        # Strategy 2: Fallback — search all text
        if monthly is None:
            full_text = soup.get_text()
            m = re.search(r"RM(\d[\d,]*).*?Kadar Gaji Minimum.*?Bulanan", full_text)
            if m:
                monthly = int(m.group(1).replace(",", ""))

        if hourly is None:
            full_text = soup.get_text()
            h = re.search(r"RM([\d.]+).*?Kadar Gaji Minimum.*?Setiap Jam", full_text)
            if h:
                hourly = float(h.group(1))

        if monthly is None:
            raise ValueError(
                "Could not parse minimum wage from MOHR portal. "
                "Page structure may have changed."
            )

        # Gazette link and reference text
        gazette_link = None
        gazette_ref = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "PUA" in href and href.endswith(".pdf"):
                gazette_link = href if href.startswith("http") else f"https://gajiminimum.mohr.gov.my{href}"
                gazette_ref = a.get_text(strip=True)
                break

        # Derive year and act from gazette reference text
        # e.g. "Warta Perintah Gaji Minimum 2024" -> year 2024, act "Minimum Wages Order 2024"
        order_year = None
        act_name = None
        if gazette_ref:
            year_match = re.search(r"(20\d{2})", gazette_ref)
            if year_match:
                order_year = int(year_match.group(1))
                # Derive act name from gazette reference
                act_name = gazette_ref.replace("Warta ", "").strip()
                if not act_name:
                    act_name = f"Minimum Wages Order {order_year}"

        # Try to extract gazette ID from PDF URL
        gazette_id = None
        if gazette_link:
            gid_match = re.search(r"PUA\s*%?(?:20)?\s*(\d+)", gazette_link, re.IGNORECASE)
            if gid_match:
                gazette_id = f"PUA {gid_match.group(1)}"

        # Extract effective dates from page
        effective_dates = self._extract_effective_dates(soup)

        # Extract notes from page
        notes = self._extract_notes(soup, effective_dates)

        # Convert first effective date to ISO format
        effective_from_iso = None
        if effective_dates:
            effective_from_iso = self._parse_date_to_iso(effective_dates[0])

        # Use effective date year if newer than gazette year
        output_year = order_year
        if effective_from_iso:
            try:
                eff_year = int(effective_from_iso[:4])
                if order_year is None or eff_year > order_year:
                    output_year = eff_year
            except (ValueError, IndexError):
                pass

        data = {
            "source": self.SOURCE_URL,
            "year": output_year,
            "effective_from": effective_from_iso,
            "gazette": gazette_id,
            "act": act_name,
            "rates": {
                "nationwide": {
                    "monthly": monthly,
                    "hourly": hourly,
                },
            },
            "min_employees_for_mandatory": 1,
            "notes": notes,
        }

        if gazette_link:
            data["gazette_url"] = gazette_link

        if self.has_changed("minimum_wage.json", data):
            return data
        return None

    def _extract_effective_dates(self, soup: BeautifulSoup) -> list[str]:
        """Extract effective dates from page content."""
        dates = []
        full_text = soup.get_text()

        # Look for effective dates
        eff_match = re.search(
            r"Tarikh[-\s]*Tarikh\s+Berkuatkuasa", full_text, re.IGNORECASE
        )
        if eff_match:
            # Found the effective dates section
            chunk = full_text[eff_match.end():eff_match.end() + 500]
            # Extract date patterns
            for m in re.finditer(r"(\d{1,2}\s+\w+\s+\d{4})", chunk):
                dates.append(m.group(1).strip())

        # Look for "Effective" dates in English
        for m in re.finditer(r"Effective\s+(\w+\s+\d{4})", full_text, re.IGNORECASE):
            dates.append(m.group(1).strip())

        # Look for "February 2025" style dates
        for m in re.finditer(r"(?:effective|berkuatkuasa)[^.]*?(\w+\s+\d{4})", full_text, re.IGNORECASE):
            date = m.group(1).strip()
            if date not in dates:
                dates.append(date)

        return dates

    def _extract_notes(self, soup: BeautifulSoup, effective_dates: list[str]) -> list[str]:
        """Extract notes from page content."""
        notes = []

        # Effective date note
        if effective_dates:
            notes.append(f"Effective {effective_dates[0]} for all employers regardless of size")
        else:
            # Look for effective date text
            full_text = soup.get_text()
            eff_match = re.search(
                r"(Effective[^.]*employers?[^.]*\.)", full_text, re.IGNORECASE
            )
            if eff_match:
                notes.append(eff_match.group(1).strip())

        # Look for nationwide/city distinction notes
        full_text = soup.get_text()
        nationwide_match = re.search(
            r"(nationwide[^.]*\.)", full_text, re.IGNORECASE
        )
        if nationwide_match:
            notes.append(nationwide_match.group(1).strip())

        # Look for supersedes/previous notes
        super_match = re.search(
            r"(Supersedes?[^.]*\.)", full_text, re.IGNORECASE
        )
        if super_match:
            notes.append(super_match.group(1).strip())

        # Look for employer size notes
        size_match = re.search(
            r"(regardless of (?:company )?size[^.]*\.)", full_text, re.IGNORECASE
        )
        if size_match:
            notes.append(size_match.group(1).strip())

        return notes

    def _parse_date_to_iso(self, date_str: str) -> str | None:
        """Convert a date string like '27 April 2026' to ISO format '2026-04-27'."""
        import calendar
        months = {name.lower(): idx for idx, name in enumerate(calendar.month_name) if name}
        months.update({name.lower(): idx for idx, name in enumerate(calendar.month_abbr) if name})

        # Pattern: "27 April 2026" or "1 February 2025"
        m = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", date_str)
        if m:
            day, month_name, year = m.groups()
            month_num = months.get(month_name.lower())
            if month_num:
                return f"{year}-{month_num:02d}-{int(day):02d}"

        # Pattern: "February 2025" or "April 2026"
        m = re.match(r"(\w+)\s+(\d{4})", date_str)
        if m:
            month_name, year = m.groups()
            month_num = months.get(month_name.lower())
            if month_num:
                return f"{year}-{month_num:02d}-01"

        return None
