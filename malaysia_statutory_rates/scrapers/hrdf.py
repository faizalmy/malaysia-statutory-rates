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

        # Extract act reference from page
        act = self._extract_act(text)

        # Extract section descriptions from page
        mandatory_desc = self._extract_section_description(text, "section 14")
        optional_desc = self._extract_section_description(text, "section 15")

        # Derive year from act reference (PSMB Act 2001) or use current year
        import datetime
        act_year_match = re.search(r"Act\s+(\d{4})", act)
        int(act_year_match.group(1)) if act_year_match else None
        current_year = datetime.datetime.now().year
        # Use current year since HRDF rates are standing
        year = current_year

        data = {
            "source": self.SOURCE_URL,
            "year": year,
            "effective_from": f"{year}-01-01",
            "act": act,
            "rates": {
                "mandatory": {
                    "rate": mandatory_rate,
                    "description": mandatory_desc,
                    "section": self._extract_section_ref(text, "14"),
                },
                "optional": {
                    "rate": optional_rate,
                    "description": optional_desc,
                    "section": self._extract_section_ref(text, "15"),
                },
                "exempted": {
                    "rate": 0.0,
                    "description": "Employers exempted from HRDF levy",
                    "section": "PSMB Act 2001",
                },
            },
            "wage_components": {
                "included": included,
                "excluded": excluded,
            },
            "notes": self._extract_notes(text, formula),
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

    def _parse_formula(self, text: str) -> str | None:
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

    def _extract_act(self, text: str) -> str:
        """Extract act reference from page text. Raises ValueError if not found."""
        # Look for "PSMB Act 2001"
        act_match = re.search(r"(PSMB\s+Act\s+\d{4})", text, re.IGNORECASE)
        if act_match:
            return act_match.group(1).strip()

        # Fallback: look for any act reference
        act_match = re.search(r"Act\s+(\d{4})\b", text, re.IGNORECASE)
        if act_match:
            return f"Act {act_match.group(1)}"

        raise ValueError("Could not extract act reference from HRDF page")

    def _extract_section_description(self, text: str, section: str) -> str | None:
        """Extract description for a section from page text."""
        # Look for text near the section reference
        idx = text.lower().find(section)
        if idx >= 0:
            chunk = text[idx:idx + 300]
            # Look for "shall be subject to" or "shall pay" sentence
            desc_match = re.search(
                r"(shall\s+(?:be\s+subject\s+to|pay).*?(?:\d+\.\d+%|employee)\.)",
                chunk,
                re.IGNORECASE | re.DOTALL,
            )
            if desc_match:
                desc = desc_match.group(0).strip()
                desc = re.sub(r"\s+", " ", desc)
                return desc

        return None

    def _extract_section_ref(self, text: str, section_num: str) -> str:
        """Extract full section reference from page text."""
        # Look for "Section X of the PSMB Act 2001"
        ref_match = re.search(
            rf"(Section\s+{section_num}\s+of\s+the\s+PSMB\s+Act\s+\d{{4}})",
            text, re.IGNORECASE,
        )
        if ref_match:
            return ref_match.group(1).strip()

        # Fallback: "Section X, PSMB Act 2001"
        ref_match = re.search(
            rf"(Section\s+{section_num}[^.]*PSMB[^.]*\d{{4}})",
            text, re.IGNORECASE,
        )
        if ref_match:
            return ref_match.group(1).strip()

        # Fallback: just the section number
        return f"Section {section_num}"

    def _extract_notes(self, text: str, formula: str | None) -> list[str]:
        """Extract notes from page text."""
        notes = []

        # Formula
        if formula:
            notes.append(formula)

        # Payment deadline - look for specific payment date
        due_match = re.search(
            r"(Payment before or on \d+/\d+/\d+,\s*payment within \d+ days of the following month)",
            text, re.IGNORECASE,
        )
        if due_match:
            note = due_match.group(1).strip()
            note = re.sub(r"\s+", " ", note)
            notes.append(note)

        return notes
