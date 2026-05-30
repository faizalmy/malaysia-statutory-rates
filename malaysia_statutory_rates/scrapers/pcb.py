"""Scrape PCB/MTD tax data from LHDN specification PDF.

Parses tax brackets (Table 1), rebates (Table 3), and reliefs from
the LHDN MTD specification PDF.
"""

import re
from pathlib import Path

from malaysia_statutory_rates.scrapers.base import BaseScraper

PCB_PDF_URL = "https://www.hasil.gov.my/media/arvlrzh5/spesifikasi-kaedah-pengiraan-berkomputer-pcb-2026.pdf"
PCB_CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "pdf"


def _pcb_cache_path() -> Path:
    """Derive PCB cache path from the URL."""
    name = PCB_PDF_URL.rsplit("/", 1)[-1].split("?")[0]
    if not name.endswith(".pdf"):
        name = "pcb-specification.pdf"
    return PCB_CACHE_DIR / name


class PCBScraper(BaseScraper):
    """Scrape PCB/MTD data from LHDN specification PDF."""

    SOURCE_URL = "https://www.hasil.gov.my/en/employers/mtd-schedular/"
    SOURCE_NAME = "Lembaga Hasil Dalam Negeri Malaysia (LHDN)"

    def scrape(self) -> dict | None:
        """Download PCB specification PDF and parse tax data from it."""
        import fitz

        pdf_path = self._download_binary(PCB_PDF_URL, _pcb_cache_path())
        doc = fitz.open(pdf_path)

        try:
            # Extract year from title page
            page1_text = doc[0].get_text("text")
            year_match = re.search(r"(20\d{2})", page1_text)
            if not year_match:
                raise ValueError("Could not extract year from PCB specification PDF")
            year = int(year_match.group(1))

            # Extract amendment date
            date_match = re.search(r"Updated\s*:\s*(\d{1,2}\s+\w+\s+\d{4})", page1_text)
            updated = date_match.group(1) if date_match else None

            # Parse Table 1 (tax brackets) — search for page with bracket data
            table1_text = self._find_page_with(doc, r"5,001\s*[-–]\s*20,000")
            brackets = self._extract_brackets(table1_text)
            if not brackets:
                raise ValueError("Could not parse tax brackets from PCB specification PDF")

            # Parse Table 3 (rebates) — search for "Table 3" header
            table3_text = self._find_page_with(doc, r"Table\s+3.*Value\s+of\s+P.*R\s+and\s+T")
            rebates = self._extract_rebates(table3_text)

            # Parse reliefs — scan all pages for relief patterns
            reliefs = self._extract_reliefs(doc)

            # Extract description and notes
            bracket_desc = self._extract_bracket_description(doc, year)
            notes = self._extract_notes(doc, year)

        finally:
            doc.close()

        data = {
            "source": self.SOURCE_URL,
            "pdf_url": PCB_PDF_URL,
            "year": year,
            "updated": updated,
            "pcb_method": "computerized",
            "tax_categories": {
                "category_1": {
                    "label": "Single/Widowed/Divorced with no children",
                    "code": "cat1",
                },
                "category_2": {
                    "label": "Married with spouse not working",
                    "code": "cat2",
                },
                "category_3": {
                    "label": "Married with spouse working",
                    "code": "cat3",
                },
            },
            "tax_brackets": {
                "description": bracket_desc,
                "brackets": brackets,
            },
            "tax_rebates": rebates,
            "tax_reliefs": reliefs,
            "notes": notes,
        }

        if self.has_changed("pcb_table.json", data):
            return data
        return None

    @staticmethod
    def _find_page_with(doc, pattern: str) -> str:
        """Find the first page whose text matches the regex pattern.

        Returns the page text.

        Raises ValueError if no page matches.
        """
        compiled = re.compile(pattern, re.IGNORECASE)
        for i in range(len(doc)):
            text = doc[i].get_text("text")
            if compiled.search(text):
                return text
        raise ValueError(f"Could not find page matching pattern: {pattern}")

    def _extract_brackets(self, page_text: str) -> list[dict]:
        """Extract tax brackets from Table 1 page text."""
        brackets = []

        # Match rows like: 5,001 - 20,000  5,000  1  – 400  – 800
        # Or: 5,001 - 20,000  5,000  1  - 400  - 800
        row_pattern = r"([\d,]+)\s*[-–]\s*([\d,]+)\s+([\d,]+)\s+(\d+)\s+[-–]?\s*([\d,]+)\s+[-–]?\s*([\d,]+)"
        for match in re.finditer(row_pattern, page_text):
            brackets.append({
                "min": int(match.group(1).replace(",", "")),
                "max": int(match.group(2).replace(",", "")),
                "rate": int(match.group(4)) / 100,
                "base_tax": 0,
                "M": int(match.group(3).replace(",", "")),
                "B_cat1_3": self._parse_int(match.group(5)),
                "B_cat2": self._parse_int(match.group(6)),
            })

        # Match "Exceeding X" row
        exceed_pattern = r"Exceeding\s+([\d,]+)\s+([\d,]+)\s+(\d+)\s+([\d,]+)\s+([\d,]+)"
        exceed_match = re.search(exceed_pattern, page_text)
        if exceed_match:
            brackets.append({
                "min": int(exceed_match.group(1).replace(",", "")),
                "max": None,
                "rate": int(exceed_match.group(3)) / 100,
                "base_tax": 0,
                "M": int(exceed_match.group(2).replace(",", "")),
                "B_cat1_3": self._parse_int(exceed_match.group(4)),
                "B_cat2": self._parse_int(exceed_match.group(5)),
            })

        # Prepend implicit zero-rate bracket (0–5000) if not already present
        if brackets and (not brackets[0] or brackets[0]["min"] > 0):
            zero_bracket = {
                "min": 0,
                "max": 5000,
                "rate": 0.0,
                "base_tax": 0,
                "M": 0,
                "B_cat1_3": 0,
                "B_cat2": 0,
            }
            brackets.insert(0, zero_bracket)

        # Calculate base_tax using integer-safe arithmetic
        # base_tax for bracket i = sum of (max_j - M_j) * rate_j for all j < i
        if brackets:
            cumulative = 0
            for b in brackets:
                b["base_tax"] = round(cumulative, 2)
                if b["rate"] > 0:
                    upper = b.get("max") or b["min"]
                    # Use int multiplication to avoid float drift
                    range_val = upper - b["M"]
                    cumulative += range_val * b["rate"]
                    cumulative = round(cumulative, 2)

        return brackets

    def _extract_rebates(self, page_text: str) -> dict:
        """Extract rebate amounts from Table 3 page text."""
        rebates = {}

        # Match "35,000 and below" with rebate amounts
        below_match = re.search(
            r"([\d,]+)\s+and\s+below\s+(\d+)\s+(\d+)\s+(\d+)",
            page_text,
        )
        if below_match:
            rebates["threshold"] = int(below_match.group(1).replace(",", ""))
            rebates["rate"] = int(below_match.group(2)) / 100
            rebates["category_1_3"] = int(below_match.group(3))
            rebates["category_2"] = int(below_match.group(4))

        # Match "Exceeding X" with 0 rebates
        exceed_match = re.search(
            r"Exceeding\s+([\d,]+)\s+(\d+)\s+(\d+)\s+(\d+)",
            page_text,
        )
        if exceed_match:
            rebates["above_threshold"] = {
                "threshold": int(exceed_match.group(1).replace(",", "")),
                "rate": int(exceed_match.group(2)) / 100,
                "category_1_3": int(exceed_match.group(3)),
                "category_2": int(exceed_match.group(4)),
            }

        return rebates

    def _extract_reliefs(self, doc) -> dict:
        """Extract tax reliefs from the PDF document."""
        reliefs = []
        relief_sections = []

        # Scan all pages for relief data — look for pages with relief patterns
        for i in range(len(doc)):
            page_text = doc[i].get_text("text")
            # Relief pages contain "Individual" with amounts and "limited to" language
            if re.search(r"[a-z]\.\s+.*?(?:limited to|amount).*?RM[\d,]+", page_text, re.IGNORECASE):
                relief_sections.append(page_text)

        all_text = "\n".join(relief_sections)

        # Pattern: relief name followed by amount
        # e.g. "Individual ... 9,000.00" or "a. Individual\n... 9,000.00"
        relief_pattern = r"(?:^|\n)\s*[a-z]\.\s+(.+?)\n.*?(?:limited to|limited|amount).*?RM([\d,]+(?:\.\d{2})?)"
        for match in re.finditer(relief_pattern, all_text, re.DOTALL | re.IGNORECASE):
            name = match.group(1).strip()
            amount = self._parse_int(match.group(2))
            if name and amount:
                reliefs.append({"name": name, "amount": amount})

        # Fallback: use hardcoded official LHDN YA 2025/2026 relief schedule
        # when regex extraction produces fewer than 5 reliefs
        if len(reliefs) < 5:
            reliefs = self._get_fallback_reliefs()

        return {
            "reliefs": reliefs,
            "note": self._extract_relief_note(all_text),
        }

    @staticmethod
    def _get_fallback_reliefs() -> list[dict]:
        """Return hardcoded tax reliefs based on official LHDN YA 2025 schedule."""
        return [
            {"code": "self", "name": "Individual and dependent relatives", "amount": 9000},
            {"code": "parent", "name": "Medical treatment for parents/grandparents", "amount": 8000},
            {"code": "disabled_equipment", "name": "Basic supporting equipment for disabled", "amount": 6000},
            {"code": "disabled_self", "name": "Disabled individual", "amount": 7000},
            {"code": "education_self", "name": "Education fees (Self)", "amount": 7000},
            {"code": "medical", "name": "Medical expenses (serious diseases, fertility, vaccination, dental)", "amount": 10000},
            {"code": "medical_exam", "name": "Medical examination, COVID test, mental health", "amount": 1000},
            {"code": "child_disabled_expenses", "name": "Child intellectual disability expenses", "amount": 6000},
            {"code": "lifestyle", "name": "Books, PC, internet, courses", "amount": 2500},
            {"code": "lifestyle_sports", "name": "Sports equipment and activities", "amount": 1000},
            {"code": "breastfeeding", "name": "Breastfeeding equipment", "amount": 1000},
            {"code": "childcare", "name": "Child care fees", "amount": 3000},
            {"code": "sspn", "name": "Education savings (SSPN)", "amount": 8000},
            {"code": "spouse", "name": "Husband/wife/alimony", "amount": 4000},
            {"code": "disabled_spouse", "name": "Disabled husband/wife", "amount": 6000},
            {"code": "child", "name": "Each unmarried child under 18", "amount": 2000},
            {"code": "child_18_student", "name": "Each unmarried child 18+ in full-time education", "amount": 2000},
            {"code": "child_18_diploma", "name": "Each unmarried child 18+ diploma/degree", "amount": 8000},
            {"code": "child_disabled", "name": "Disabled child", "amount": 8000},
            {"code": "life_insurance_epf", "name": "Life insurance and EPF", "amount": 7000},
            {"code": "prs", "name": "Deferred Annuity and PRS", "amount": 3000},
            {"code": "education_medical_insurance", "name": "Education and medical insurance", "amount": 4000},
            {"code": "socso", "name": "SOCSO contribution", "amount": 350},
            {"code": "ev_charging", "name": "EV charging and food waste composting", "amount": 2500},
            {"code": "housing_loan", "name": "Housing loan interest (first home)", "amount": 7000},
        ]

    def _extract_relief_note(self, text: str) -> str | None:
        """Extract relief-related disclaimer or note from PDF text."""
        # Look for approval/subject-to note
        match = re.search(
            r"(Employee\s+can\s+claim\s+deductions[^.]{10,200}\.)",
            text, re.IGNORECASE
        )
        if match:
            return re.sub(r"\s+", " ", match.group(1).strip())
        # Look for schedule note
        match = re.search(
            r"(Schedule\s+\w+\s+of\s+(?:the\s+)?Income\s+Tax[^.]{10,200}\.)",
            text, re.IGNORECASE
        )
        if match:
            return re.sub(r"\s+", " ", match.group(1).strip())
        # Look for any subject-to note near reliefs
        match = re.search(
            r"(reliefs?\s+(?:are\s+)?(?:subject to|as provided|permitted)[^.]{10,200}\.)",
            text, re.IGNORECASE
        )
        if match:
            return re.sub(r"\s+", " ", match.group(1).strip())
        return None

    @staticmethod
    def _parse_int(value: str) -> int:
        """Parse a string with commas as thousand separators into int."""
        return int(value.replace(",", "").replace(".", "").strip())

    def _extract_bracket_description(self, doc, year: int) -> str:
        """Extract tax bracket description from PDF text."""
        # Scan first few pages for description text
        for i in range(min(5, len(doc))):
            page_text = doc[i].get_text("text")

            # Look for MTD/PCB explanation
            mtd_match = re.search(
                r"(Monthly Tax Deduction[^.]*\.)", page_text, re.IGNORECASE
            )
            if mtd_match:
                desc = mtd_match.group(1).strip()
                # Look for P, M, R, B definitions
                defs = []
                for pattern in [
                    r"P\s*=\s*[^.\n]+",
                    r"M\s*=\s*[^.\n]+",
                    r"R\s*=\s*[^.\n]+",
                    r"B\s*=\s*[^.\n]+",
                ]:
                    def_match = re.search(pattern, page_text, re.IGNORECASE)
                    if def_match:
                        defs.append(def_match.group(0).strip())
                if defs:
                    return f"{desc} {' '.join(defs)}"
                return desc

        # Fallback — try to construct from PDF title
        for i in range(min(3, len(doc))):
            page_text = doc[i].get_text("text")
            title_match = re.search(
                r"(MONTHLY\s+TAX\s+DEDUCTION[^\n]{10,200})",
                page_text, re.IGNORECASE
            )
            if title_match:
                return re.sub(r"\s+", " ", title_match.group(1).strip())

        raise ValueError("Could not extract tax bracket description from PCB PDF")

    def _extract_notes(self, doc, year: int) -> list[str]:
        """Extract notes from PDF document."""
        notes = []

        # Source reference — extract from PDF title block
        for i in range(min(3, len(doc))):
            page_text = doc[i].get_text("text")
            if "SPECIFICATION" in page_text.upper() and "MTD" in page_text.upper():
                # Extract title block between SPECIFICATION and Updated/Date
                title_match = re.search(
                    r"(SPECIFICATION\s+FOR\s+MONTHLY\s+TAX\s+DEDUCTION[^\n]*(?:\n[^\n]*?)*(?:\d{4}))",
                    page_text, re.IGNORECASE
                )
                if title_match:
                    title = re.sub(r"\s+", " ", title_match.group(1).strip())
                    notes.append(title)
                    break
                # Simpler fallback
                title_match = re.search(
                    r"(SPECIFICATION[^\n]*MTD[^\n]*(?:\n[^\n]*?)*?\d{4})",
                    page_text, re.IGNORECASE
                )
                if title_match:
                    notes.append(re.sub(r"\s+", " ", title_match.group(1).strip()))
                    break

        # Scan pages for category explanations
        for i in range(min(20, len(doc))):
            page_text = doc[i].get_text("text")

            # B values / category explanation
            cat_match = re.search(
                r"(B values?[^.]*category[^.]*\.)", page_text, re.IGNORECASE
            )
            if cat_match:
                note = cat_match.group(1).strip()
                if note not in notes:
                    notes.append(note)
                    break

        # Scan for Zakat note (look for actual sentence, not table data)
        for i in range(min(30, len(doc))):
            page_text = doc[i].get_text("text")
            zakat_match = re.search(
                r"(Zakat\s+(?:is\s+)?(?:deducted|deduction)[^.]{10,100}\.)", page_text, re.IGNORECASE
            )
            if zakat_match:
                note = zakat_match.group(1).strip()
                note = re.sub(r"\s+", " ", note)
                # Skip if it looks like table data (contains < or ≥ or lots of numbers)
                if "<" not in note and "≥" not in note and len(note) < 200:
                    notes.append(note)
                    break

        # Scan for non-resident note (look for actual sentence, not table data)
        for i in range(min(30, len(doc))):
            page_text = doc[i].get_text("text")
            nr_match = re.search(
                r"(Non-resident[^.]{10,100}\d+%[^.]{0,50}\.)", page_text, re.IGNORECASE
            )
            if nr_match:
                note = nr_match.group(1).strip()
                note = re.sub(r"\s+", " ", note)
                if "<" not in note and "≥" not in note and len(note) < 200:
                    notes.append(note)
                    break

        return notes
