# malaysia-statutory-rates

Open-source Malaysian statutory rate data — EPF, SOCSO, EIS, PCB, minimum wage, HRDF, public holidays.

**Scraper + data only.** No calculation engine.

## Install

```bash
pip install malaysia-statutory-rates
```

For scraping capabilities:

```bash
pip install malaysia-statutory-rates[scraper]
```

## Quick Start

### Python

```python
from malaysia_statutory_rates import load_rates

rates = load_rates()

# EPF rates
epf = rates["epf_rates"]
employee_rate = epf["rates"]["malaysian_pr_nonmy_before_aug98_below_60"]["employee"]["rate"]  # 0.11
employer_rate = epf["rates"]["malaysian_pr_nonmy_before_aug98_below_60"]["employer"]["wage_lte_5000"]["rate"]  # 0.13

# Minimum wage
mw = rates["minimum_wage"]
min_salary = mw["rates"]["nationwide"]["monthly"]  # 1700

# SOCSO wage ceiling
socso = rates["socso_rates"]
ceiling = socso["wage_ceiling"]  # 6000

# Public holidays
holidays = rates["public_holidays"]
national = [h for h in holidays["holidays"] if h.get("national")]
```

### CLI

```bash
# Show all rates
malaysia-rates show

# Show specific rate
malaysia-rates show epf
malaysia-rates show minimum-wage
malaysia-rates show holidays

# Run scrapers to update data
malaysia-rates scrape --all
```

## Data Files

| File | Source | Content |
|---|---|---|
| `data/epf_rates.json` | kwsp.gov.my | EPF contribution rates by citizenship, age, wage bracket |
| `data/socso_rates.json` | perkeso.gov.my + booklet PDF | SOCSO metadata + 65-bracket rate table (2 schedules) |
| `data/eis_rates.json` | perkeso.gov.my + booklet PDF | EIS metadata + 65-bracket rate table |
| `data/pcb_table.json` | LHDN e-CP39 | PCB/MTD tax brackets and reliefs |
| `data/minimum_wage.json` | gajiminimum.mohr.gov.my | Minimum wage (monthly + hourly) |
| `data/hrdf_rates.json` | hrdcorp.gov.my | HRDF levy rates and formula |
| `data/public_holidays.json` | publicholidays.com.my | National + state public holidays |
| `data/foreign_worker_rates.json` | Combined | EPF/SOCSO/EIS rates for foreign workers |

## Scraping

Scrapers fetch live data from official government websites. Most sites are scraped directly with httpx. Sites that block automated requests (like kwsp.gov.my) fall back to [Firecrawl](https://firecrawl.dev).

### Setup

```bash
# Install scraper dependencies
pip install malaysia-statutory-rates[scraper]

# Copy .env and add your Firecrawl API key (optional, only needed for blocked sites)
cp .env.example .env
```

### Run

```bash
# Run all scrapers
malaysia-rates scrape --all

# Via Python
from malaysia_statutory_rates.scrapers import run_scrapers
results = run_scrapers()  # {"epf_rates": True, "minimum_wage": False, ...}
```

### How it works

1. Checks local cache (`.cache/fetch/`) — returns if < 24h old
2. Checks `robots.txt` — skips if URL is disallowed
3. Each scraper tries httpx first (fast, no API cost)
4. On 403/429 or JS-only SPA shell, falls back to Firecrawl (uses 1 credit)
5. Successful responses cached for 24 hours to save credits
6. Data is saved to `data/*.json` with `_metadata` (scraped_at, source)
7. Change detection — only writes if data actually changed

### Sources

| Source | Method | Notes |
|---|---|---|
| kwsp.gov.my (EPF) | Firecrawl fallback | Returns 403 to httpx |
| perkeso.gov.my (SOCSO/EIS) | httpx + PDF parse | Metadata from HTML; rate tables from booklet PDF |
| gajiminimum.mohr.gov.my | httpx | Minimum wage gazette |
| hrdcorp.gov.my (HRDF) | Firecrawl fallback | JS SPA — httpx gets empty shell |
| publicholidays.com.my | httpx | Third-party, scrapes table |
| LHDN (PCB) | Manual | e-CP39 requires login |

## Scraper Status

| Scraper | Status | Data Source | Notes |
|---|---|---|---|
| `minimum_wage.py` | ✅ Complete | HTML scrape | Rates, gazette, year all from source page |
| `hrdf.py` | ✅ Complete | Firecrawl HTML | Rates, wage components, formula parsed from HTML |
| `holidays.py` | ✅ Complete | HTML scrape | Year, holidays scraped dynamically |
| `epf.py` | ✅ Complete | HTML scrape | Year, effective_from, act, age_limits from page |
| `socso.py` | ✅ Complete | HTML + PDF | Metadata from page; 65-bracket rate table parsed live from PERKESO booklet |
| `eis.py` | ✅ Complete | HTML + PDF | Metadata from page; 65-bracket rate table parsed live from PERKESO booklet |
| `pcb_table.json` | ❌ No scraper | Manual | LHDN e-CP39 requires login |
| `foreign_worker_rates.json` | ✅ Generated | Derived | Computed from EPF/SOCSO/EIS scraper output |

### PDF Parsing

SOCSO and EIS rate tables (65 wage brackets each) are parsed live from the
[PERKESO 2025 Booklet](https://www.perkeso.gov.my/images/dokumen/risalah/2025-BOOKLET_PERKESO_BI.pdf)
— a text-based PDF with clean embedded text (no OCR needed). The parser uses
pymupdf to extract table data from specific pages (36–39 for Act 4, 52–55 for Act 800).

The booklet PDF is cached at `.cache/pdf/2025-BOOKLET_PERKESO_BI.pdf`.

### Roadmap

**Phase 1 — Easy metadata fixes (no PDF parsing):** ✅ Done
- [x] `epf.py`: extract year, effective_from, act, age_limits from page
- [x] `socso.py`: extract year, effective_from, scheme descriptions from page
- [x] `eis.py`: extract year, effective_from, act name from page

**Phase 2 — Derived data:** ✅ Done
- [x] `foreign_worker_rates`: generate from existing EPF/SOCSO/EIS scraper output

**Phase 3 — PDF parsing for rate tables:** ✅ Done
- [x] Find high-quality PDF source — PERKESO 2025 Booklet (text-based, 74 pages)
- [x] Integrate PDF parser (`pdf_parser.py`) with pymupdf — extracts 65-bracket tables
- [x] Remove seed data dependency, generate `rate_table` from PDF at scrape time
- [x] Cache booklet PDF in `.cache/pdf/`

**Phase 4 — New scraper:**
- [ ] `pcb_table`: scrape LHDN page for tax brackets and reliefs

## What This Is NOT

This library provides **data only**. It does NOT:
- Calculate payroll
- Calculate tax (PCB)
- Determine which rates apply to a specific employee

## Disclaimer

This data is scraped from official government websites for reference only. Always verify rates against [official sources](DISCLAIMER.md) before making payroll or tax decisions. Use at your own risk.

## License

MIT
