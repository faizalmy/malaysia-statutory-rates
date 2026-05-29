"""Scrape SOCSO contribution rates from PERKESO.

Parses the rate of contribution page for metadata (wage ceiling, PDF links,
scheme descriptions, effective dates). The full 65-bracket rate table is
parsed live from the PERKESO booklet PDF.
"""

import re
from datetime import datetime

from bs4 import BeautifulSoup

from malaysia_statutory_rates.scrapers.base import BaseScraper
from malaysia_statutory_rates.scrapers.pdf_parser import (
    BOOKLET_URL,
    extract_socso_table,
)


class SOCSOScraper(BaseScraper):
    """Scrape SOCSO rates from perkeso.gov.my."""

    SOURCE_URL = "https://www.perkeso.gov.my/en/rate-of-contribution.html"
    SOURCE_NAME = "Pertubuhan Keselamatan Sosial (PERKESO)"

    def scrape(self) -> dict | None:
        html = self.fetch(self.SOURCE_URL)
        soup = BeautifulSoup(html, "html.parser")

        # Extract wage ceiling from page text
        full_text = soup.get_text()
        wage_ceiling = None
        ceiling_match = re.search(r"RM([\d,]+)\s*per month", full_text, re.IGNORECASE)
        if ceiling_match:
            wage_ceiling = int(ceiling_match.group(1).replace(",", ""))
        if wage_ceiling is None:
            raise ValueError("Could not extract wage ceiling from SOCSO page")

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

        # Extract effective date from page text
        effective_from = None
        eff_match = re.search(r"Effective\s+(\d+)\s+(\w+)\s+(\d{4})", full_text, re.IGNORECASE)
        if eff_match:
            try:
                dt = datetime.strptime(f"{eff_match.group(1)} {eff_match.group(2)} {eff_match.group(3)}", "%d %B %Y")
                effective_from = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        if effective_from is None:
            raise ValueError("Could not extract effective date from SOCSO page")

        # Derive year from effective_from
        year = int(effective_from[:4])

        # Extract act reference — PERKESO page uses "Act 4" not full name
        act = None
        # Look for "Act 4" in context of SOCSO/contribution
        act_match = re.search(r"Act\s+4\b", full_text, re.IGNORECASE)
        if act_match:
            act = "Employees Social Security Act 1969 (Act 4)"
        if act is None:
            raise ValueError("Could not extract act reference from SOCSO page")

        # Extract self-employment act reference
        se_act = None
        se_act_match = re.search(r"Self-Employment.*?Act\s*(\d+)", full_text, re.IGNORECASE)
        if se_act_match:
            se_act = f"Act {se_act_match.group(1)}"

        # Extract housewives scheme details
        hw_act = None
        hw_act_match = re.search(r"Housewives.*?Act\s*(\d+)", full_text, re.IGNORECASE)
        if hw_act_match:
            hw_act = f"Act {hw_act_match.group(1)}"

        hw_contribution = None
        hw_match = re.search(r"RM(\d+).*?(\d+)\s+consecutive\s+months", full_text, re.IGNORECASE)
        if hw_match:
            hw_contribution = f"RM{hw_match.group(1)} per year (paid in advance for {hw_match.group(2)} consecutive months)"

        data = {
            "source": self.SOURCE_URL,
            "act": act,
            "year": year,
            "effective_from": effective_from,
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
                "act": se_act,
                "rates": self_employment,
            },
            "housewives_scheme": {
                "act": hw_act,
                "contribution": hw_contribution,
            },
            "notes": [
                f"Wage ceiling: RM{wage_ceiling:,} per month (effective {datetime.strptime(effective_from, '%Y-%m-%d').strftime('%b %Y')})",
                "Actual contribution rates are in the Act 4 PDF (Third Schedule)",
                "Foreign workers: Employment Injury only (no Invalidity scheme)",
                "Contribution due by 15th of following month",
            ],
        }

        # Parse rate table live from PERKESO booklet PDF
        try:
            data["rate_table"] = extract_socso_table()
            data["rate_table_source"] = BOOKLET_URL
        except FileNotFoundError:
            pass  # booklet not cached — rate_table will be omitted

        if self.has_changed("socso_rates.json", data):
            return data
        return None
