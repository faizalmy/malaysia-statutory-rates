# malaysia-statutory-rates

Open-source Malaysian statutory rate data. Scraper + data only.

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
employee_rate = epf["rates"]["citizen_below_60"]["employee"]["rate"]  # 0.11

# Minimum wage
mw = rates["minimum_wage"]
min_salary = mw["rates"]["nationwide"]["monthly"]  # 1700
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
| `data/socso_rates.json` | perkeso.gov.my | SOCSO rates (Employment Injury + Invalidity) |
| `data/eis_rates.json` | perkeso.gov.my | EIS contribution rates |
| `data/pcb_table.json` | hasil.gov.my | PCB/MTD tax deduction tables |
| `data/minimum_wage.json` | mohr.gov.my | Minimum wage by area type |
| `data/hrdf_rates.json` | hrdcorp.gov.my | HRDF levy rates |
| `data/public_holidays.json` | moha.gov.my | National + state public holidays |
| `data/foreign_worker_rates.json` | Combined | EPF/SOCSO/EIS rates for foreign workers |

## What This Is NOT

This library provides **data only**. It does NOT:
- Calculate payroll
- Calculate tax (PCB)
- Determine which rates apply to a specific employee

You build the calculation logic. We provide the rates.

## Data Sources

All data is scraped from official Malaysian government websites.

## License

MIT
