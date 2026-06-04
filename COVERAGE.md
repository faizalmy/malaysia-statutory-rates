# Coverage Gaps

This document tracks known data coverage gaps and derivation decisions.

## Foreign Worker Rates

**Status:** Derived from EPF/SOCSO/EIS main rates

Foreign worker rates in `foreign_worker_rates.json` are derived from the main
EPF, SOCSO, and EIS rate files. The derivation rules are:

### EPF
- Foreign workers registered **before 1 Aug 1998**: same rates as Malaysian PR
- Foreign workers registered **from 1 Aug 1998**: separate rate category
  (currently: employee 0%, employer varies by wage bracket)
- Legal reference: EPF Act 1991, Section 43(1), Third Schedule

### SOCSO
- Foreign workers are covered under **Employment Injury Scheme only** (not Invalidity)
- Same wage ceiling (RM6,000) and rate table as Malaysian workers (Schedule 1)
- Legal reference: Employees Social Security Act 1969 (Act 4)

### EIS
- Foreign workers are **not covered** under EIS (Act 800)
- The `foreign_worker_rates.json` includes EIS wage ceiling for reference only
- Legal reference: Employment Insurance System Act 2017 (Act 800)

## PCB (Tax) Data

**Status:** Manually verified

PCB data is extracted from LHDN's Computerized Method Specification
(`spesifikasi-kaedah-pengiraan-berkomputer-pcb-2026.pdf`).

- The e-CP39 portal requires authentication, so PCB data is **not automatically scraped**
- Data is manually extracted and verified against the official PDF specification
- Tax brackets, rebates, and reliefs are from the 2026 specification
- Users should verify against [hasil.gov.my](https://www.hasil.gov.my) for the latest rates

## State Public Holidays

**Status:** 13 states + 3 Federal Territories covered

| State/FT | Status | Notes |
|---|---|---|
| Johor | ✅ Covered | |
| Kedah | ✅ Covered | |
| Kelantan | ✅ Covered | |
| Melaka | ✅ Covered | |
| Negeri Sembilan | ✅ Covered | |
| Pahang | ✅ Covered | |
| Perak | ✅ Covered | |
| Perlis | ✅ Covered | |
| Penang | ✅ Covered | |
| Sabah | ✅ Covered | |
| Sarawak | ✅ Covered | |
| Selangor | ✅ Covered | |
| Terengganu | ✅ Covered | |
| Kuala Lumpur | ✅ Federal Territory | |
| Labuan | ✅ Federal Territory | |
| Putrajaya | ✅ Federal Territory | |

Source: [publicholidays.com.my](https://publicholidays.com.my)

Note: State holidays are scraped from a third-party source, not directly from
government gazettes. Some states may have additional district-level holidays
not captured here.

## Historical Rates

**Status:** Not supported — current rates only

This package provides **current rates only**. Historical rate data is not
maintained. Reasons:

1. Government websites typically show only current rates
2. Historical data would require scraping gazette archives or manual entry
3. The versioning strategy (patch bumps for data changes) means users can pin
   a specific version to get a point-in-time snapshot

**Workaround for historical data:**
- Pin a package version: `pip install malaysia-statutory-rates==0.1.2`
- Each version's data is immutable once published
- The `_changelog.jsonl` tracks all changes going forward from v0.2.0+
- For pre-v0.2.0 history, check git commits

## Rate Tables (SOCSO/EIS)

**Status:** Complete — 65 wage brackets each

SOCSO and EIS rate tables are parsed from the PERKESO 2025 Booklet PDF.
Each table has 65 wage brackets covering wages from RM0 to RM6,000+.

- SOCSO: 2 schedules (Employment Injury + Invalidity)
- EIS: 1 schedule (equal employer/employee split)

The rate tables include contribution amounts per bracket, not just percentages,
making them directly usable for payroll calculations.
