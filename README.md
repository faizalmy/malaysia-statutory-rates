# Malaysia Statutory Rates

Malaysian statutory rate data — EPF, SOCSO, EIS, PCB, minimum wage, HRDF, public holidays.

Data only, no calculation engine.

## Install

```bash
pip install malaysia-statutory-rates
```

## Usage

### Python

```python
from malaysia_statutory_rates import load_rates

rates = load_rates()

# EPF rates
epf = rates["epf_rates"]
employee_rate = epf["rates"]["malaysian_pr_nonmy_before_aug98_below_60"]["employee"]["rate"]  # 0.11

# Minimum wage
mw = rates["minimum_wage"]
min_salary = mw["rates"]["nationwide"]["monthly"]  # 1700

# SOCSO wage ceiling
socso = rates["socso_rates"]
ceiling = socso["wage_ceiling"]  # 6000

# Public holidays
holidays = rates["public_holidays"]
national = holidays["national"]  # list of national holidays
```

### CLI

```bash
malaysia-statutory-rates show           # all rates
malaysia-statutory-rates show epf       # specific rate
malaysia-statutory-rates status         # data freshness
malaysia-statutory-rates changelog      # change history
```

## Data Files

| File | Content |
|---|---|
| `epf_rates.json` | EPF contribution rates by citizenship, age, wage bracket |
| `socso_rates.json` | SOCSO rates (65 wage brackets, 2 schedules) |
| `eis_rates.json` | EIS rates (65 wage brackets) |
| `pcb_table.json` | PCB/MTD tax brackets and reliefs |
| `minimum_wage.json` | Minimum wage (monthly + hourly) |
| `hrdf_rates.json` | HRDF levy rates |
| `public_holidays.json` | National + state public holidays |
| `foreign_worker_rates.json` | EPF/SOCSO/EIS for foreign workers |

All data in `malaysia_statutory_rates/data/`. Each file includes `_metadata.scraped_at` for freshness.

## Disclaimer

Data scraped from official government websites. Verify rates against [official sources](DISCLAIMER.md) before making payroll or tax decisions.

## License

MIT
