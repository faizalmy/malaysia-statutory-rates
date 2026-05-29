"""Scrape SOCSO contribution rates from PERKESO.

Parses the rate of contribution page. The actual rate tables are in PDFs,
but the HTML page has the wage ceiling, scheme descriptions, and PDF links.
"""

import re

from bs4 import BeautifulSoup

from malaysia_statutory_rates.scrapers.base import BaseScraper


class SOCSOScraper(BaseScraper):
    """Scrape SOCSO rates from perkeso.gov.my."""

    SOURCE_URL = "https://www.perkeso.gov.my/en/rate-of-contribution.html"
    SOURCE_NAME = "Pertubuhan Keselamatan Sosial (PERKESO)"

    def scrape(self) -> dict | None:
        html = self.fetch(self.SOURCE_URL)
        soup = BeautifulSoup(html, "html.parser")

        # Extract wage ceiling from page text
        full_text = soup.get_text()
        wage_ceiling = 6000  # default
        ceiling_match = re.search(r"RM([\d,]+)\s*per month", full_text, re.IGNORECASE)
        if ceiling_match:
            wage_ceiling = int(ceiling_match.group(1).replace(",", ""))

        # Extract PDF links
        act4_pdf = None
        act800_pdf = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.endswith(".pdf"):
                if "ACT 4" in href.upper() or "ACT4" in href.upper():
                    act4_pdf = href if href.startswith("http") else f"https://www.perkeso.gov.my{href}"
                elif "ACT 800" in href.upper() or "ACT800" in href.upper():
                    act800_pdf = href if href.startswith("http") else f"https://www.perkeso.gov.my{href}"

        # Extract self-employment rates from HTML table
        self_employment = []
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) >= 3:
                    earning = cols[1].get_text(strip=True)
                    monthly = cols[2].get_text(strip=True)
                    if "RM" in earning:
                        self_employment.append({
                            "insured_monthly_earning": earning,
                            "contribution_monthly": monthly,
                        })

        # Extract contribution update announcement
        announcement = ""
        for h in soup.find_all(["h1", "h2", "h3"]):
            text = h.get_text(strip=True)
            if "wage ceiling" in text.lower() or "contribution amount" in text.lower():
                announcement = text
                break

        data = {
            "source": self.SOURCE_URL,
            "act": "Employees Social Security Act 1969 (Act 4)",
            "year": 2025,
            "effective_from": "2024-10-01",
            "wage_ceiling": wage_ceiling,
            "pdf_url": act4_pdf,
            "announcement": announcement,
            "schemes": {
                "employment_injury": {
                    "full_name": "Employment Injury Scheme",
                    "employer_only": True,
                    "note": "Rate in Third Schedule (Act 4) PDF. Covers workplace accidents, commuting, occupational diseases.",
                },
                "invalidity": {
                    "full_name": "Invalidity Scheme",
                    "note": "Rate in Third Schedule (Act 4) PDF. Covers permanent disability not related to employment.",
                },
            },
            "self_employment_scheme": {
                "act": "Act 789",
                "rates": self_employment,
            },
            "housewives_scheme": {
                "act": "Act 838",
                "contribution": "RM120 per year (paid in advance for 12 months)",
            },
            "notes": [
                f"Wage ceiling: RM{wage_ceiling:,} per month (effective Oct 2024)",
                "Actual contribution rates are in the Act 4 PDF (Third Schedule)",
                "Foreign workers: Employment Injury only (no Invalidity scheme)",
                "Contribution due by 15th of following month",
            ],
        }

        if self.has_changed("socso_rates.json", data):
            return data
        return None
