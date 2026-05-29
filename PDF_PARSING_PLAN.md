# Plan: PDF Parsing for SOCSO/EIS Rate Tables

## Context

SOCSO (Act 4) and EIS (Act 800) scrapers currently extract metadata from HTML but
the actual contribution rate tables are only in linked PDFs. Both PDFs are
IMAGE-BASED (scanned documents) — no embedded text, requires OCR.

## Source PDFs

| PDF | URL | Content |
|-----|-----|---------|
| Act 4 | perkeso.gov.my/images/dokumen/151124-Rate Contribution ACT 4.pdf | 65 wage brackets × 4 columns |
| Act 800 | perkeso.gov.my/images/dokumen/151124-Rate Contribution ACT 800.pdf | 65 wage brackets × 3 columns |

Both use identical wage bracket structure: RM0–RM6,000 cap, 65 rows.
Contributions are FIXED RM amounts per bracket (not percentages).

## Approach: Firecrawl PDF Parse → Table Extraction

### Step 1: PDF Download + Cache

- Download PDFs via httpx (direct URL, no auth needed)
- Cache to `.cache/pdfs/` with 24h TTL (same pattern as `.cache/fetch/`)
- Filename: SHA256(url)[:16].pdf
- Add `_download_pdf(url)` helper to BaseScraper

### Step 2: Parse PDF Tables

Try in order:
1. **Firecrawl parse** (`firecrawl_parse` with JSON schema) — if it handles scanned PDFs
2. **pymupdf + Tesseract OCR** — fallback for image-based PDFs
   - `pip install pymupdf pytesseract` (tesseract binary via `brew install tesseract`)
   - Extract images from PDF → OCR → parse table rows
3. **pdfplumber** — if PDF has any embedded table structure

The subagent research found OCR works but needs cleanup (e.g. "RM5SO" → "RM50").
We'll validate extracted data: 65 rows, monotonically increasing RM values, sums check.

### Step 3: Update SOCSO Scraper

Add `_parse_pdf_tables(pdf_path)` to socso.py:
- Parse Act 4 PDF → 65 rows with columns:
  - employer_schedule1 (EI + INV employer share)
  - employee_schedule1 (INV employee share)
  - total_schedule1 (employer + employee)
  - total_schedule2 (EI only, employer pays all)
- Add `"rate_table"` key to output dict with parsed rows
- Derive component rates: `ei_employer = col4`, `inv_share = col2`

Output structure addition:
```json
{
  "rate_table": {
    "schedule_1": [
      {"wage_min": 0, "wage_max": 30, "employer": 0.4, "employee": 0.1, "total": 0.5},
      ...
    ],
    "schedule_2": [
      {"wage_min": 0, "wage_max": 30, "employer": 0.3, "employee": 0, "total": 0.3},
      ...
    ],
    "wage_ceiling": 6000,
    "brackets": 65
  }
}
```

### Step 4: Update EIS Scraper

Same pattern, parse Act 800 PDF → 65 rows with columns:
- employee, employer, total (equal split)

Output structure addition:
```json
{
  "rate_table": [
    {"wage_min": 0, "wage_max": 30, "employer": 0.05, "employee": 0.05, "total": 0.1},
    ...
  ],
  "wage_ceiling": 6000,
  "brackets": 65
}
```

### Step 5: Shared PDF Utilities

Create `malaysia_statutory_rates/scrapers/pdf_utils.py`:
- `download_pdf(url, cache_dir)` — download with 24h cache
- `parse_pdf_tables(pdf_path)` — try Firecrawl → OCR → pdfplumber
- `validate_table(rows, expected_cols)` — row count, monotonicity, sum checks

### Step 6: Tests

Update tests/test_socso_eis.py:
- `test_socso_rate_table_exists` — rate_table key present
- `test_socso_rate_table_65_brackets` — 65 rows
- `test_socso_rate_table_sums` — employer + employee = total
- `test_eis_rate_table_exists`
- `test_eis_rate_table_65_brackets`
- `test_eis_rate_table_equal_split` — employer == employee

### Step 7: Dependencies

Add to pyproject.toml [scraper] extras:
```
pymupdf>=1.24.0
pytesseract>=0.3.10
```

## Execution Order

1. Install tesseract binary (`brew install tesseract`)
2. Add pymupdf + pytesseract to pyproject.toml
3. Create pdf_utils.py (download, parse, validate)
4. Update socso.py — add PDF parsing, rate_table in output
5. Update eis.py — add PDF parsing, rate_table in output
6. Update tests
7. Run full test suite
8. Commit

## Risks

- **OCR accuracy**: Scanned PDFs may have misrecognized chars. Mitigated by
  validation (row count, monotonicity, sum checks) and regex cleanup.
- **tesseract dependency**: Binary must be installed. Falls back gracefully if
  not available (skips PDF parsing, keeps existing behavior).
- **Firecrawl PDF parse**: May not handle image-based PDFs well. OCR is the
  reliable fallback.
- **PDF URL changes**: PERKESO may change PDF URLs. Scraper already extracts
  URLs from HTML, so new URLs are picked up automatically.
