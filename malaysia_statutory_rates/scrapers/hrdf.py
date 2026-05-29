"""Scrape HRDF levy rates from HRD Corp."""

import re

from bs4 import BeautifulSoup

from malaysia_statutory_rates.scrapers.base import BaseScraper


class HRDFScraper(BaseScraper):
    """Scrape HRDF levy rates from hrdcorp.gov.my."""

    SOURCE_URL = "https://supportcentre.hrdcorp.gov.my/portal/en/kb/articles/hrd-levy"
    SOURCE_NAME = "HRD Corporation of Malaysia (HRD Corp)"

    def scrape(self) -> dict | None:
        html = self.fetch(self.SOURCE_URL)
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()

        # Extract rates from page text
        # Section 14: mandatory 1%
        # Section 15: optional 0.5%
        mandatory_rate = self._extract_rate(text, "section 14")
        optional_rate = self._extract_rate(text, "section 15")

        if mandatory_rate is None:
            raise ValueError("Could not extract mandatory HRDF rate from page")
        if optional_rate is None:
            raise ValueError("Could not extract optional HRDF rate from page")

        # Parse wage components from page
        included, excluded = self._parse_wage_components(text)

        # Parse levy formula
        formula = self._parse_formula(text)

        data = {
            "source": self.SOURCE_URL,
            "act": "PSMB Act 2001 (Act 612)",
            "rates": {
                "mandatory": {
                    "rate": mandatory_rate,
                    "description": "Employers with 10 or more Malaysian employees",
                    "section": "Section 14, PSMB Act 2001",
                },
                "optional": {
                    "rate": optional_rate,
                    "description": "Employers with fewer than 10 Malaysian employees (voluntary registration)",
                    "section": "Section 15, PSMB Act 2001",
                },
            },
            "wage_components": {
                "included": included,
                "excluded": excluded,
            },
            "notes": [
                formula if formula else "Formula not found on page",
                "Payment due by 15th of following month",
                "Exempted sectors may change — check hrdcorp.gov.my/circulars",
            ],
        }

        if self.has_changed("hrdf_rates.json", data):
            return data
        return None

    def _extract_rate(self, text: str, section: str) -> float | None:
        """Extract levy rate percentage near a section reference. Returns None if not found."""
        # Find the section text and look for "X% of the monthly wage(s)" nearby
        idx = text.lower().find(section)
        if idx >= 0:
            chunk = text[idx:idx + 500]
            m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*of\s*the\s*monthly\s*wage", chunk, re.IGNORECASE)
            if m:
                return float(m.group(1)) / 100

        # Broader pattern
        pattern = rf"{section}.*?(?:levy|rate).*?(\d+(?:\.\d+)?)\s*%"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return float(match.group(1)) / 100

        return None

    def _parse_wage_components(self, text: str) -> tuple[list[str], list[str]]:
        """Parse included/excluded wage components from page text."""
        included = []
        excluded = []

        # --- Included components ---
        # Text pattern: "WagesBasic salary and fixed allowance ... and includes
        # any leave pay and arrears of wages but DOES NOT INCLUDE"
        # Note: "Wages" may be concatenated with "Basic" (no space)
        wages_match = re.search(
            r"Wages\s*Basic\s+salary(.*?)but\s+DOES\s+NOT\s+INCLUDE",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if wages_match:
            wages_text = wages_match.group(1)
            wages_text = wages_text.replace("\xa0", " ").strip()

            if "basic salary" in wages_text.lower() or "basic salary" in "wages basic salary":
                included.append("Basic salary")
            if "fixed allowance" in wages_text.lower():
                included.append("Fixed allowances")
            if "leave pay" in wages_text.lower():
                included.append("Leave pay")
            if "arrears of wages" in wages_text.lower():
                included.append("Arrears of wages")

        # --- Excluded components ---
        # "DOES NOT INCLUDE" section: items like "any pension fund, retrenchment..."
        does_not_match = re.search(
            r"DOES\s+NOT\s+INCLUDE\s*:\s*[-\xa0]*\s*-?\s*any\s+(.*?)(?:Example|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if does_not_match:
            chunk = does_not_match.group(1)
            # Items are "-any X-any Y-any Z" pattern
            items = re.split(r"[-\xa0]+any\s+", chunk)
            for item in items:
                item = item.strip().strip('"').strip("\u201c\u201d").strip()
                # Remove trailing text artifacts
                item = re.sub(r"\s*\.\.\.\s*.*$", "", item)
                item = re.sub(r"\s*\u2026\s*.*$", "", item)
                # Cut off at "Example" if it appears
                item = re.split(r"(?i)example", item)[0].strip()
                if item and len(item) > 3:
                    item = item[0].upper() + item[1:] if item else item
                    excluded.append(item)

        # "Example of wages Exempted" section: dash-separated items
        exempt_match = re.search(
            r"Example\s+of\s+wages\s+Exempted.*?:\s*[-\xa0]*(.*?)(?:Example\s+of\s+non|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if exempt_match:
            chunk = exempt_match.group(1)
            # Items separated by dash before capital letter: "commissions-Gratuity"
            items = re.split(r"(?<=[a-z.)])-+(?=[A-Z])", chunk)
            for item in items:
                item = item.strip().strip("-").strip()
                if item and len(item) > 3:
                    excluded.append(item)

        # "Example of non-fixed allowance Exempted" section
        nonfixed_match = re.search(
            r"non-fixed\s+allowance\s+Exempted.*?:\s*[-\xa0]*(.*?)(?:Example\s*:\s*Current|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if nonfixed_match:
            chunk = nonfixed_match.group(1)
            items = re.split(r"(?<=[a-z.)])-+(?=[A-Z])", chunk)
            for item in items:
                item = item.strip().strip("-").strip()
                if item and len(item) > 3:
                    excluded.append(item)

        return included, excluded

    def _parse_formula(self, text: str) -> str:
        """Parse the levy formula from the page."""
        # Look for "LEVY = [(BASIC SALARY - UNPAID LEAVE) + FIXED ALLOWANCE] x 1%"
        formula_match = re.search(
            r"LEVY\s*=\s*\[.*?\]\s*x\s*\d+(?:\.\d+)?%",
            text,
            re.IGNORECASE,
        )
        if formula_match:
            formula = formula_match.group(0).strip()
            # Clean up unicode artifacts
            formula = formula.replace("\u200b", "")
            formula = formula.replace("\\", "")
            formula = re.sub(r"\s+", " ", formula)
            return formula

        return None
