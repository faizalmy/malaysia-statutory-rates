# malaysia-statutory-rates

Malaysian statutory rate data — EPF, SOCSO, EIS, PCB, minimum wage, HRDF, public holidays.

Data only, no calculation engine.

## Install

```bash
pip install malaysia-statutory-rates
```

For scraping:

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
malaysia-rates show
malaysia-rates show epf
malaysia-rates show holidays
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
| `data/foreign_worker_rates.json` | Derived | EPF/SOCSO/EIS rates for foreign workers |

## Scraping

Scrapers fetch data from government websites. httpx is used first; blocked sites (kwsp.gov.my, hrdcorp.gov.my) fall back to [Firecrawl](https://firecrawl.dev).

### Setup

```bash
pip install malaysia-statutory-rates[scraper]
cp .env.example .env  # add Firecrawl API key if needed
```

### Run

```bash
malaysia-rates scrape --all
```

```python
from malaysia_statutory_rates.scrapers import run_scrapers
results = run_scrapers()  # {"epf_rates": True, "minimum_wage": False, ...}
```

### How it works

1. Checks local cache (`.cache/fetch/`) — returns if < 24h old
2. Checks `robots.txt` — skips if disallowed
3. Tries httpx first (no API cost)
4. Falls back to Firecrawl on 403/429 or JS-only pages (1 credit)
5. Caches responses for 24 hours
6. Writes to `data/*.json` with `_metadata` (scraped_at, source)
7. Change detection — only writes if data changed

### Sources

| Source | Method | Notes |
|---|---|---|
| kwsp.gov.my (EPF) | Firecrawl fallback | Returns 403 to httpx |
| perkeso.gov.my (SOCSO/EIS) | httpx + PDF parse | Metadata from HTML; rate tables from booklet PDF |
| gajiminimum.mohr.gov.my | httpx | Minimum wage gazette |
| hrdcorp.gov.my (HRDF) | Firecrawl fallback | JS SPA — httpx gets empty shell |
| publicholidays.com.my | httpx | Third-party, scrapes table |
| LHDN (PCB) | Manual | e-CP39 requires login |

### Scraper Status

| Scraper | Status | Data Source |
|---|---|---|
| `minimum_wage.py` | Done | HTML |
| `hrdf.py` | Done | Firecrawl HTML |
| `holidays.py` | Done | HTML |
| `epf.py` | Done | HTML |
| `socso.py` | Done | HTML + PDF |
| `eis.py` | Done | HTML + PDF |
| `pcb_table.json` | No scraper | Manual — LHDN e-CP39 requires login |
| `foreign_worker_rates.json` | Done | Derived from EPF/SOCSO/EIS |

### PDF Parsing

SOCSO and EIS rate tables (65 wage brackets each) are parsed from the
[PERKESO 2025 Booklet](https://www.perkeso.gov.my/images/dokumen/risalah/2025-BOOKLET_PERKESO_BI.pdf)
using pymupdf. Pages 36–39 for Act 4, 52–55 for Act 800.

Cached at `.cache/pdf/2025-BOOKLET_PERKESO_BI.pdf`.

### Todo

- [ ] `pcb_table`: scrape LHDN page for tax brackets and reliefs

## Disclaimer

Data scraped from official government websites. Verify rates against [official sources](DISCLAIMER.md) before making payroll or tax decisions.

## License

MIT
