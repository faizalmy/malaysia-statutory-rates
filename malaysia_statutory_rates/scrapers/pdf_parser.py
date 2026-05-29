"""Parse contribution rate tables from PERKESO booklet PDF.

Extracts Act 4 (SOCSO) and Act 800 (EIS) rate tables from the
text-based PERKESO booklet using pymupdf (no OCR needed).

Table pages are located by searching for header text, not hardcoded page numbers.
"""

import re
from pathlib import Path

import fitz  # pymupdf

# PERKESO booklet URL
BOOKLET_URL = "https://www.perkeso.gov.my/images/dokumen/risalah/2025-BOOKLET_PERKESO_BI.pdf"

# Cache directory for downloaded PDFs
BOOKLET_CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "pdf"

# Header patterns used to locate rate tables inside the booklet PDF
# Act 4: match the "ACT 4 CONTRIBUTION SCHEDULE" heading on the table page
_ACT4_HEADER = re.compile(r"ACT\s+4\s+CONTRIBUTION\s+SCHEDULE", re.IGNORECASE)
# Act 800: match the table column headers (No. / Monthly Wages / Employer / Employee / Total)
_ACT800_HEADER = re.compile(
    r"No\.\s*\n\s*Monthly\s+Wages\s*\n\s*Employer.*?Contribution\s*\n\s*Employee.*?Contribution\s*\n\s*Total",
    re.IGNORECASE | re.DOTALL,
)


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


def get_booklet_path() -> Path:
    """Return path to cached booklet PDF."""
    # Find the most recent cached PERKESO booklet PDF
    candidates = sorted(BOOKLET_CACHE_DIR.glob("*BOOKLET*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    if candidates:
        return candidates[0]
    # Derive filename from URL
    filename = BOOKLET_URL.rsplit("/", 1)[-1].split("?")[0]
    return BOOKLET_CACHE_DIR / filename


def _download_booklet() -> Path:
    """Download the PERKESO booklet PDF if not cached."""
    import httpx

    path = get_booklet_path()
    if path.exists():
        return path

    BOOKLET_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"    Downloading PERKESO booklet from {BOOKLET_URL}...")
    resp = httpx.get(BOOKLET_URL, follow_redirects=True, timeout=60)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    print(f"    Downloaded {len(resp.content)} bytes to {path}")
    return path


def _find_table_pages(doc: fitz.Document, header_pattern: re.Pattern,
                      num_cols: int, max_pages: int = 10) -> tuple[int, int]:
    """Find the start/end page range for a rate table by searching for its header.

    Searches for the header pattern, then verifies the page contains actual
    table data (column headers like "No." and "Monthly Wages") before returning.
    This avoids matching the table of contents or summary pages.

    Args:
        doc: Opened pymupdf document.
        header_pattern: Regex to match the table header text.
        num_cols: Expected number of amount columns (used for validation).
        max_pages: Max pages to scan after header match.

    Returns:
        (start_page, end_page) tuple (0-indexed, end exclusive).

    Raises:
        ValueError if the table header is not found.
    """
    for i in range(len(doc)):
        text = doc[i].get_text("text")
        if not header_pattern.search(text):
            continue

        # Verify this page has actual table column headers, not just TOC entries
        if "Monthly Wages" not in text:
            continue

        # Found header page with table data — scan forward for extent
        start = i
        end = i + 1
        for j in range(i + 1, min(i + max_pages, len(doc))):
            page_text = doc[j].get_text("text")
            # Check if this page still has table data (row numbers)
            if re.search(r"^\d+\s*$", page_text, re.MULTILINE):
                end = j + 1
            else:
                break
        return start, end

    raise ValueError(f"Could not find table matching header pattern: {header_pattern.pattern}")


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


def extract_socso_table(doc: fitz.Document | None = None) -> list[dict]:
    """Extract Act 4 (SOCSO) 65-bracket rate table.

    Returns list of dicts with keys:
        row, wage_min, wage_max,
        employer_schedule1, employee_schedule1, total_schedule1, total_schedule2
    """
    close_doc = doc is None
    if doc is None:
        path = _download_booklet()
        doc = fitz.open(path)

    try:
        start, end = _find_table_pages(doc, _ACT4_HEADER, num_cols=4)
        raw = _extract_table(doc, start, end, num_cols=4)
    finally:
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
        path = _download_booklet()
        doc = fitz.open(path)

    try:
        start, end = _find_table_pages(doc, _ACT800_HEADER, num_cols=3)
        raw = _extract_table(doc, start, end, num_cols=3)
    finally:
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
