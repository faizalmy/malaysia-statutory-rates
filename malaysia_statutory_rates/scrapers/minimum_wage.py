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
        act_name = "Minimum Wages Order 2024"
        if gazette_ref:
            year_match = re.search(r"(20\d{2})", gazette_ref)
            if year_match:
                order_year = int(year_match.group(1))
                act_name = f"Minimum Wages Order {order_year}"

        # Try to extract gazette ID from PDF URL
        gazette_id = None
        if gazette_link:
            gid_match = re.search(r"PUA\s*%?20?(\d+)", gazette_link, re.IGNORECASE)
            if gid_match:
                gazette_id = f"PUA {gid_match.group(1)}"

        data = {
            "source": self.SOURCE_URL,
            "year": order_year or 2025,
            "gazette": gazette_id or "PUA 376",
            "act": act_name,
            "rates": {
                "nationwide": {
                    "monthly": monthly,
                    "hourly": hourly,
                },
            },
            "min_employees_for_mandatory": 1,
            "notes": [
                "Effective February 2025 for all employers regardless of size",
                "Supersedes previous RM1,500 (cities) / RM1,200 (other areas) tiers",
                "Applies nationwide — no distinction between city and other areas",
            ],
        }

        if gazette_link:
            data["gazette_url"] = gazette_link

        if self.has_changed("minimum_wage.json", data):
            return data
        return None
