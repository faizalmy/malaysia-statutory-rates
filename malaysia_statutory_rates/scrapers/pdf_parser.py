"""Parse contribution rate tables from PERKESO booklet PDF.

Extracts Act 4 (SOCSO) and Act 800 (EIS) rate tables from the
text-based PERKESO booklet using pymupdf (no OCR needed).
"""

import re
from pathlib import Path

import fitz  # pymupdf

# PERKESO booklet URL and page ranges
BOOKLET_URL = "https://www.perkeso.gov.my/images/dokumen/risalah/2025-BOOKLET_PERKESO_BI.pdf"
BOOKLET_CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "pdf"
BOOKLET_FILENAME = "2025-BOOKLET_PERKESO_BI.pdf"

# 0-indexed page ranges for rate tables in the booklet
ACT4_PAGES = (35, 39)    # pages 36-39
ACT800_PAGES = (51, 55)  # pages 52-55


def _parse_amount(text: str) -> float | None:
    """Parse 'RM1.10' or '40 cents' or 'RM1,234.50' to float."""
    text = text.strip()
    m = re.match(r"RM([\d, ]+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1).replace(",", "").replace(" ", ""))
    m = re.match(r"(\d+)\s*cents?", text, re.IGNORECASE)
    if m:
        return int(m.group(1)) / 100
    return None


def _extract_table(doc: fitz.Document, page_start: int, page_end: int,
                   num_cols: int) -> list[dict]:
    """Extract a rate table from booklet pages.

    Args:
        doc: Opened pymupdf document.
        page_start: First page index (0-based, inclusive).
        page_end: Last page index (0-based, exclusive).
        num_cols: Number of amount columns to extract.

    Returns:
        List of dicts with row, wage_min, wage_max, and amount fields.
    """
    rows = []
    for page_num in range(page_start, page_end):
        page = doc[page_num]
        text = page.get_text("text")
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]

            # Skip headers and non-data lines
            if line in ("No.",) or line.startswith(("Monthly Wages", "First Category",
                        "Employment Injury", "Second Category", "Employer")):
                i += 1
                continue

            # Match standalone row number
            num_match = re.match(r"^(\d+)$", line)
            if not num_match:
                i += 1
                continue

            row_num = int(num_match.group(1))

            # Next line(s): wage description
            if i + 1 >= len(lines):
                i += 1
                continue

            wage_line = lines[i + 1]
            wage_min = wage_max = None
            lines_consumed = 1  # how many extra lines the wage description spans

            up_to = re.search(r"up to\s*RM([\d, ]+)", wage_line, re.IGNORECASE)
            if up_to:
                wage_min, wage_max = 0, int(up_to.group(1).replace(",", "").replace(" ", ""))
            else:
                exceeds = re.findall(r"exceed\s*RM([\d, ]+)", wage_line, re.IGNORECASE)
                if len(exceeds) >= 2:
                    wage_min = int(exceeds[0].replace(",", "").replace(" ", ""))
                    wage_max = int(exceeds[1].replace(",", "").replace(" ", ""))
                elif len(exceeds) == 1:
                    wage_min = int(exceeds[0].replace(",", "").replace(" ", ""))
                    # Wage max may be on the next line
                    if i + 2 < len(lines):
                        next_exceed = re.search(
                            r"exceed\s*RM([\d, ]+)", lines[i + 2], re.IGNORECASE
                        )
                        if next_exceed:
                            wage_max = int(next_exceed.group(1).replace(",", "").replace(" ", ""))
                            lines_consumed = 2

            # Collect amount values after the wage description
            amounts = []
            j = i + 1 + lines_consumed
            while j < len(lines) and len(amounts) < num_cols:
                val = _parse_amount(lines[j])
                if val is not None:
                    amounts.append(val)
                elif re.match(r"^\d+$", lines[j]) and int(lines[j]) == row_num + 1:
                    break  # next row started
                j += 1

            if len(amounts) == num_cols and wage_min is not None:
                rows.append({
                    "row": row_num,
                    "wage_min": wage_min,
                    "wage_max": wage_max,
                    "amounts": amounts,
                })

            i += 1

    return rows


def get_booklet_path() -> Path:
    """Return path to cached booklet PDF."""
    return BOOKLET_CACHE_DIR / BOOKLET_FILENAME


def extract_socso_table(doc: fitz.Document | None = None) -> list[dict]:
    """Extract Act 4 (SOCSO) 65-bracket rate table.

    Returns list of dicts with keys:
        row, wage_min, wage_max,
        employer_schedule1, employee_schedule1, total_schedule1, total_schedule2
    """
    close_doc = doc is None
    if doc is None:
        path = get_booklet_path()
        if not path.exists():
            raise FileNotFoundError(
                f"PERKESO booklet not found at {path}. "
                f"Download from {BOOKLET_URL}"
            )
        doc = fitz.open(path)

    raw = _extract_table(doc, *ACT4_PAGES, num_cols=4)

    if close_doc:
        doc.close()

    return [
        {
            "row": r["row"],
            "wage_min": r["wage_min"],
            "wage_max": r["wage_max"],
            "employer_schedule1": r["amounts"][0],
            "employee_schedule1": r["amounts"][1],
            "total_schedule1": r["amounts"][2],
            "total_schedule2": r["amounts"][3],
        }
        for r in raw
    ]


def extract_eis_table(doc: fitz.Document | None = None) -> list[dict]:
    """Extract Act 800 (EIS) 65-bracket rate table.

    Returns list of dicts with keys:
        row, wage_min, wage_max, employer, employee, total
    """
    close_doc = doc is None
    if doc is None:
        path = get_booklet_path()
        if not path.exists():
            raise FileNotFoundError(
                f"PERKESO booklet not found at {path}. "
                f"Download from {BOOKLET_URL}"
            )
        doc = fitz.open(path)

    raw = _extract_table(doc, *ACT800_PAGES, num_cols=3)

    if close_doc:
        doc.close()

    return [
        {
            "row": r["row"],
            "wage_min": r["wage_min"],
            "wage_max": r["wage_max"],
            "employer": r["amounts"][0],
            "employee": r["amounts"][1],
            "total": r["amounts"][2],
        }
        for r in raw
    ]
