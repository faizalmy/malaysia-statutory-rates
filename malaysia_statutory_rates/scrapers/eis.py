"""Scrape EIS contribution rates from PERKESO.

EIS (Act 800) shares the same source page as SOCSO (Act 4).
The full 65-bracket rate table is parsed live from the PERKESO booklet PDF.
"""

import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from malaysia_statutory_rates.scrapers.base import BaseScraper
from malaysia_statutory_rates.scrapers.pdf_parser import extract_eis_table

# PERKESO booklet PDF URL (shared with SOCSO scraper)
BOOKLET_URL = "https://www.perkeso.gov.my/images/dokumen/risalah/2025-BOOKLET_PERKESO_BI.pdf"
BOOKLET_CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "pdf"


class EISScraper(BaseScraper):
    """Scrape EIS rates from perkeso.gov.my."""

    SOURCE_URL = "https://www.perkeso.gov.my/en/rate-of-contribution.html"
    SOURCE_NAME = "Pertubuhan Keselamatan Sosial (PERKESO)"

    def scrape(self) -> dict | None:
        html = self.fetch(self.SOURCE_URL)
        soup = BeautifulSoup(html, "html.parser")

        # Extract wage ceiling
        full_text = soup.get_text()
        wage_ceiling = None
        ceiling_match = re.search(r"RM([\d,]+)\s*per month", full_text, re.IGNORECASE)
        if ceiling_match:
            wage_ceiling = int(ceiling_match.group(1).replace(",", ""))
        if wage_ceiling is None:
            raise ValueError("Could not extract wage ceiling from EIS page")

        # Extract Act 800 PDF link
        act800_pdf = None
        for a in soup.find_all("a", href=True):
            href = str(a["href"])
            if href.endswith(".pdf") and ("ACT 800" in href.upper() or "ACT800" in href.upper()):
                act800_pdf = href if href.startswith("http") else f"https://www.perkeso.gov.my{href}"
                break

        # Find EIS mention on the page
        eis_description = None
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if "0.4%" in text or "0.2%" in text or "employment insurance" in text.lower():
                eis_description = text
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
            raise ValueError("Could not extract effective date from EIS page")

        # Derive year from effective_from
        year = int(effective_from[:4])

        # Extract act reference — PERKESO page uses "Act 800" not full name
        act = None
        act_match = re.search(r"Act\s+800\b", full_text, re.IGNORECASE)
        if act_match:
            act = "Employment Insurance System Act 2017 (Act 800)"
        if act is None:
            raise ValueError("Could not extract act reference from EIS page")

        data = {
            "source": self.SOURCE_URL,
            "act": act,
            "year": year,
            "effective_from": effective_from,
            "wage_ceiling": wage_ceiling,
            "pdf_url": act800_pdf,
            "description": eis_description,
            "notes": self._extract_notes(full_text, wage_ceiling, act800_pdf),
        }

        # Download PERKESO booklet and parse rate table
        try:
            import fitz
            booklet_path = self._download_binary(BOOKLET_URL, BOOKLET_CACHE_DIR / BOOKLET_URL.rsplit("/", 1)[-1])
            doc = fitz.open(booklet_path)
            try:
                data["rate_table"] = extract_eis_table(doc)
                data["rate_table_source"] = BOOKLET_URL
            finally:
                doc.close()
        except Exception as e:
            print(f"    WARNING: Could not parse EIS rate table: {e}")

        if self.has_changed("eis_rates.json", data):
            return data
        return None

    def _extract_notes(self, text: str, wage_ceiling: int, act800_pdf: str | None) -> list[str]:
        """Extract notes from page text."""
        notes = []

        # Wage ceiling note
        notes.append(f"Wage ceiling: RM{wage_ceiling:,} per month (same as SOCSO)")

        # Look for rate schedule reference
        schedule_match = re.search(
            r"(EIS rates?[^.]*\.)", text, re.IGNORECASE
        )
        if schedule_match:
            notes.append(schedule_match.group(1).strip())
        else:
            schedule_match = re.search(
                r"(Second Schedule[^.]*\.)", text, re.IGNORECASE
            )
            if schedule_match:
                notes.append(schedule_match.group(1).strip())
            elif act800_pdf:
                notes.append(f"EIS rates are in the Act 800 PDF (Second Schedule)")

        # Look for equal contribution note
        equal_match = re.search(
            r"(Both employer and employee[^.]*\.)", text, re.IGNORECASE
        )
        if equal_match:
            notes.append(equal_match.group(1).strip())
        else:
            equal_match = re.search(
                r"(contribute equally[^.]*\.)", text, re.IGNORECASE
            )
            if equal_match:
                notes.append(equal_match.group(1).strip())

        # Look for foreign worker coverage (filter out navigation text)
        fw_match = re.search(
            r"(Foreign workers? (?:are |is )[^.]{10,200}\.)", text, re.IGNORECASE
        )
        if fw_match:
            note = fw_match.group(1).strip()
            note = re.sub(r"\s+", " ", note)
            if len(note) < 300:  # Skip navigation text which is very long
                notes.append(note)

        return notes
