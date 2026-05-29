"""Scrape SOCSO contribution rates from PERKESO.

Parses the rate of contribution page for metadata (wage ceiling, PDF links,
scheme descriptions, effective dates). The full 65-bracket rate table is
parsed live from the PERKESO booklet PDF.
"""

import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from malaysia_statutory_rates.scrapers.base import BaseScraper
from malaysia_statutory_rates.scrapers.pdf_parser import extract_socso_table

# PERKESO booklet PDF URL
BOOKLET_URL = "https://www.perkeso.gov.my/images/dokumen/risalah/2025-BOOKLET_PERKESO_BI.pdf"
BOOKLET_CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "pdf"


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
            href = str(a["href"])
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

        # Extract scheme details from page text
        schemes = self._extract_schemes(full_text, act4_pdf)

        data = {
            "source": self.SOURCE_URL,
            "act": act,
            "year": year,
            "effective_from": effective_from,
            "wage_ceiling": wage_ceiling,
            "pdf_url": act4_pdf,
            "announcement": announcement,
            "schemes": schemes,
            "self_employment_scheme": {
                "act": se_act,
                "rates": self_employment,
            },
            "housewives_scheme": {
                "act": hw_act,
                "contribution": hw_contribution,
            },
            "notes": self._extract_notes(full_text, wage_ceiling, effective_from),
        }

        # Download PERKESO booklet and parse rate table
        try:
            import fitz
            booklet_path = self._download_binary(BOOKLET_URL, BOOKLET_CACHE_DIR / BOOKLET_URL.rsplit("/", 1)[-1])
            doc = fitz.open(booklet_path)
            try:
                data["rate_table"] = extract_socso_table(doc)
                data["rate_table_source"] = BOOKLET_URL
            finally:
                doc.close()
        except Exception as e:
            print(f"    WARNING: Could not parse SOCSO rate table: {e}")

        if self.has_changed("socso_rates.json", data):
            return data
        return None

    def _extract_schemes(self, text: str, act4_pdf: str | None) -> dict:
        """Extract scheme details from page text."""
        schemes = {}

        # Employment Injury Scheme — look for scheme name in text
        ei_name = "Employment Injury Scheme"
        ei_match = re.search(r"(Employment\s+Injury\s+Scheme)", text, re.IGNORECASE)
        if ei_match:
            ei_name = ei_match.group(1).strip()

        # Look for description of what EI covers
        ei_note_parts = []
        if act4_pdf:
            ei_note_parts.append(f"Rate in Third Schedule (Act 4) PDF")
        coverage_match = re.search(
            r"(workplace\s+accidents?[^.]*\.)", text, re.IGNORECASE
        )
        if coverage_match:
            ei_note_parts.append(coverage_match.group(1).strip())
        commuting_match = re.search(
            r"(commuting[^.]*\.)", text, re.IGNORECASE
        )
        if commuting_match:
            ei_note_parts.append(commuting_match.group(1).strip())

        schemes["employment_injury"] = {
            "full_name": ei_name,
            "employer_only": True,
            "note": " ".join(ei_note_parts) if ei_note_parts else None,
        }

        # Invalidity Scheme
        inv_name = "Invalidity Scheme"
        inv_match = re.search(r"(Invalidity\s+Scheme)", text, re.IGNORECASE)
        if inv_match:
            inv_name = inv_match.group(1).strip()

        inv_note_parts = []
        if act4_pdf:
            inv_note_parts.append(f"Rate in Third Schedule (Act 4) PDF")
        disability_match = re.search(
            r"(permanent\s+disability[^.]*\.)", text, re.IGNORECASE
        )
        if disability_match:
            inv_note_parts.append(disability_match.group(1).strip())

        schemes["invalidity"] = {
            "full_name": inv_name,
            "note": " ".join(inv_note_parts) if inv_note_parts else None,
        }

        return schemes

    def _extract_notes(self, text: str, wage_ceiling: int, effective_from: str) -> list[str]:
        """Extract notes from page text."""
        notes = []

        # Wage ceiling note (dynamic)
        try:
            formatted_date = datetime.strptime(effective_from, "%Y-%m-%d").strftime("%b %Y")
            notes.append(f"Wage ceiling: RM{wage_ceiling:,} per month (effective {formatted_date})")
        except ValueError:
            notes.append(f"Wage ceiling: RM{wage_ceiling:,} per month")

        # Look for notes about where to find rates
        rate_ref_match = re.search(
            r"(Actual contribution rates?[^.]*\.)", text, re.IGNORECASE
        )
        if rate_ref_match:
            notes.append(rate_ref_match.group(1).strip())
        else:
            # Try to find PDF/schedule reference
            schedule_match = re.search(
                r"(Third Schedule[^.]*\.)", text, re.IGNORECASE
            )
            if schedule_match:
                notes.append(schedule_match.group(1).strip())

        # Look for foreign worker notes (filter out navigation text)
        fw_match = re.search(
            r"(Foreign workers? (?:are |is )[^.]{10,200}\.)", text, re.IGNORECASE
        )
        if fw_match:
            note = fw_match.group(1).strip()
            note = re.sub(r"\s+", " ", note)
            if len(note) < 300:
                notes.append(note)

        # Look for payment deadline
        due_match = re.search(
            r"(Contribution[s]? (?:are )?due[^.]*\.)", text, re.IGNORECASE
        )
        if due_match:
            notes.append(due_match.group(1).strip())
        else:
            # Try alternate pattern
            due_match = re.search(
                r"(15th[^.]*month[^.]*\.)", text, re.IGNORECASE
            )
            if due_match:
                notes.append(due_match.group(1).strip())

        return notes
