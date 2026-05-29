"""Scrape EIS contribution rates from PERKESO.

EIS (Act 800) shares the same source page as SOCSO (Act 4).
The actual rates are in the Act 800 PDF.
"""

import re

from bs4 import BeautifulSoup

from malaysia_statutory_rates.scrapers.base import BaseScraper


class EISScraper(BaseScraper):
    """Scrape EIS rates from perkeso.gov.my."""

    SOURCE_URL = "https://www.perkeso.gov.my/en/rate-of-contribution.html"
    SOURCE_NAME = "Pertubuhan Keselamatan Sosial (PERKESO)"

    def scrape(self) -> dict | None:
        html = self.fetch(self.SOURCE_URL)
        soup = BeautifulSoup(html, "html.parser")

        # Extract wage ceiling
        full_text = soup.get_text()
        wage_ceiling = 6000
        ceiling_match = re.search(r"RM([\d,]+)\s*per month", full_text, re.IGNORECASE)
        if ceiling_match:
            wage_ceiling = int(ceiling_match.group(1).replace(",", ""))

        # Extract Act 800 PDF link
        act800_pdf = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.endswith(".pdf") and ("ACT 800" in href.upper() or "ACT800" in href.upper()):
                act800_pdf = href if href.startswith("http") else f"https://www.perkeso.gov.my{href}"
                break

        # Find EIS mention on the page
        eis_description = ""
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if "0.4%" in text or "0.2%" in text or "employment insurance" in text.lower():
                eis_description = text
                break

        data = {
            "source": self.SOURCE_URL,
            "act": "Employment Insurance System Act 2017 (Act 800)",
            "year": 2025,
            "effective_from": "2024-10-01",
            "wage_ceiling": wage_ceiling,
            "pdf_url": act800_pdf,
            "description": eis_description or "EIS covers retrenchment, voluntary separation, and retirement",
            "note": "Actual contribution rates are in the Act 800 PDF (Second Schedule)",
            "notes": [
                f"Wage ceiling: RM{wage_ceiling:,} per month (same as SOCSO)",
                "EIS rates are in the Act 800 PDF (Second Schedule)",
                "Both employer and employee contribute equally",
                "Foreign workers are also covered under EIS",
            ],
        }

        if self.has_changed("eis_rates.json", data):
            return data
        return None
