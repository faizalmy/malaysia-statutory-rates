"""Scrape PCB/MTD tax data from LHDN specification PDF.

Downloads the LHDN MTD specification PDF, parses tax brackets (Table 1),
rebates (Table 3), and reliefs from the document text.
"""

import re
from pathlib import Path

import httpx

from malaysia_statutory_rates.scrapers.base import BaseScraper


PCB_PDF_URL = "https://www.hasil.gov.my/media/arvlrzh5/spesifikasi-kaedah-pengiraan-berkomputer-pcb-2026.pdf"
PCB_CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "pdf"
PCB_FILENAME = "pcb-2026-specification.pdf"


class PCBScraper(BaseScraper):
    """Scrape PCB/MTD data from LHDN specification PDF."""

    SOURCE_URL = "https://www.hasil.gov.my/en/employers/mtd-schedular/"
    SOURCE_NAME = "Lembaga Hasil Dalam Negeri Malaysia (LHDN)"

    def scrape(self) -> dict | None:
        """Download PCB specification PDF and parse tax data from it."""
        pdf_path = self._download_pdf()

        try:
            import fitz
        except ImportError:
            raise ImportError("pymupdf is required for PCB PDF parsing: pip install pymupdf")

        doc = fitz.open(pdf_path)

        # Extract year from title page
        page1_text = doc[0].get_text("text")
        year_match = re.search(r"(20\d{2})", page1_text)
        if not year_match:
            raise ValueError("Could not extract year from PCB specification PDF")
        year = int(year_match.group(1))

        # Extract amendment date
        date_match = re.search(r"Updated\s*:\s*(\d{1,2}\s+\w+\s+\d{4})", page1_text)
        updated = date_match.group(1) if date_match else None

        # Parse Table 1 (tax brackets) from page 12
        table1_text = doc[11].get_text("text")
        brackets = self._extract_brackets(table1_text)
        if not brackets:
            raise ValueError("Could not parse tax brackets from PCB specification PDF")

        # Parse Table 3 (rebates) from page 17
        table3_text = doc[16].get_text("text")
        rebates = self._extract_rebates(table3_text)

        # Parse reliefs from pages 27-36
        reliefs = self._extract_reliefs(doc)

        doc.close()

        data = {
            "source": self.SOURCE_URL,
            "year": year,
            "updated": updated,
            "specification_pdf": str(pdf_path),
            "tax_brackets": {
                "description": f"Tax brackets for Monthly Tax Deduction (MTD/PCB) {year}. "
                "P = total chargeable income per year. M = first chargeable income in range. "
                "R = tax rate. B = tax on M after individual rebate.",
                "brackets": brackets,
            },
            "tax_reliefs": reliefs,
            "notes": [
                f"Source: LHDN Specification for MTD Calculations {year}",
                "B values differ by category: Cat 1&3 (single/married-spouse-working) vs Cat 2 (spouse not working)",
                "Zakat deducted monthly from MTD, not from chargeable income",
                "Non-resident employees taxed at flat 30% of remuneration",
            ],
        }

        if self.has_changed("pcb_table.json", data):
            return data
        return None

    def _download_pdf(self) -> Path:
        """Download and cache the PCB specification PDF."""
        PCB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        pdf_path = PCB_CACHE_DIR / PCB_FILENAME

        # Check cache (valid for 7 days)
        if pdf_path.exists():
            import time
            age = time.time() - pdf_path.stat().st_mtime
            if age < 7 * 24 * 60 * 60:
                print(f"    PCB PDF: cached ({pdf_path})")
                return pdf_path

        print(f"    Downloading PCB specification PDF...")
        resp = httpx.get(PCB_PDF_URL, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        pdf_path.write_bytes(resp.content)
        print(f"    Downloaded {len(resp.content)} bytes to {pdf_path}")
        return pdf_path

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

        # Calculate base_tax from cumulative B values
        if brackets:
            prev_b = 0
            for b in brackets:
                b["base_tax"] = prev_b
                prev_b += ((b.get("max", 0) or b["min"]) - b["M"] + 1) * b["rate"] if b["rate"] > 0 else 0

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

        # Scan pages 27-36 for relief data
        for i in range(26, min(36, len(doc))):
            page_text = doc[i].get_text("text")
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

        return {
            "description": "Individual income tax reliefs",
            "reliefs": reliefs,
            "note": "Reliefs extracted from PDF text — verify against official LHDN specification",
        }

    @staticmethod
    def _parse_int(value: str) -> int:
        """Parse a string with commas as thousand separators into int."""
        return int(value.replace(",", "").replace(".", "").strip())
