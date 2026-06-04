# Malaysia Statutory Rates

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
malaysia-statutory-rates show
malaysia-statutory-rates show epf
malaysia-statutory-rates show holidays
malaysia-statutory-rates scrape --all
malaysia-statutory-rates changelog          # view data change history
malaysia-statutory-rates changelog --last 5 # last 5 entries
```

## Data Files (malaysia_statutory_rates/data/)

| File | Source | Content |
|---|---|---|
| `epf_rates.json` | kwsp.gov.my | EPF contribution rates by citizenship, age, wage bracket |
| `socso_rates.json` | perkeso.gov.my + booklet PDF | SOCSO metadata + 65-bracket rate table (2 schedules) |
| `eis_rates.json` | perkeso.gov.my + booklet PDF | EIS metadata + 65-bracket rate table |
| `pcb_table.json` | LHDN e-CP39 | PCB/MTD tax brackets and reliefs |
| `minimum_wage.json` | gajiminimum.mohr.gov.my | Minimum wage (monthly + hourly) |
| `hrdf_rates.json` | hrdcorp.gov.my | HRDF levy rates and formula |
| `public_holidays.json` | publicholidays.com.my | National + state public holidays |
| `foreign_worker_rates.json` | Derived | EPF/SOCSO/EIS rates for foreign workers |

## Scraping

Scrapers fetch data from government websites. httpx is used first; blocked sites (kwsp.gov.my, hrdcorp.gov.my) fall back to [Firecrawl](https://firecrawl.dev).

`firecrawl` is included in the `[scraper]` extras.

### Setup

```bash
pip install malaysia-statutory-rates[scraper]
cp .env.example .env  # add Firecrawl API key if needed
```

### Run

```bash
malaysia-statutory-rates scrape --all
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
8. Audit changelog — appends field-level diffs to `data/_changelog.jsonl`

### Audit Changelog

Every scrape that detects changes writes a field-level diff to `data/_changelog.jsonl`.
This enables:

- **Change tracking** — when did a rate actually change, and what specifically changed
- **Error detection** — spot suspicious jumps (e.g. EPF rate 13% → 80%)
- **Investigation** — trace which scrape introduced a bad value

```bash
# View all changes
malaysia-statutory-rates changelog

# Last 5 entries
malaysia-statutory-rates changelog --last 5
```

```python
from malaysia_statutory_rates.changelog import read_changelog
from pathlib import Path

entries = read_changelog(Path("malaysia_statutory_rates/data"), last_n=10)
for entry in entries:
    print(entry["scraper"], entry["ts"], entry["change_count"], "changes")
```

### Versioning Strategy

**Hybrid approach** — code follows semver, data updates are patch bumps:

| Change type | Version bump | Example |
|---|---|---|
| Bug fix / feature in code | Minor or patch | `0.1.1` → `0.2.0` |
| Data update (rate changed) | Patch | `0.2.0` → `0.2.1` |
| Breaking API change | Major | `0.2.1` → `1.0.0` |

**Rationale:**
- Users can `pip install --upgrade` to get latest data without API breakage
- Patch bumps are cheap — automated scraper can bump and publish
- Semver signals code stability separately from data freshness
- `_metadata.scraped_at` in each data file tells you exactly when data was last updated

**Data freshness check:**
```python
from malaysia_statutory_rates import load_rates
rates = load_rates()
print(rates["epf_rates"]["_metadata"]["scraped_at"])  # 2025-06-03T09:00:00+00:00
```

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
| `pcb.py` | Done | PDF download + metadata (data manually verified against LHDN spec) |
| `foreign_worker_rates.json` | Done | Derived from EPF/SOCSO/EIS |

### PDF Parsing

SOCSO and EIS rate tables (65 wage brackets each) are parsed from the
[PERKESO 2025 Booklet](https://www.perkeso.gov.my/images/dokumen/risalah/2025-BOOKLET_PERKESO_BI.pdf)
using pymupdf. Pages 36–39 for Act 4, 52–55 for Act 800.

## Disclaimer

Data scraped from official government websites. Verify rates against [official sources](DISCLAIMER.md) before making payroll or tax decisions.

## License

MIT
