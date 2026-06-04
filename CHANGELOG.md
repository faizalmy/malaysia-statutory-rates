# Changelog

## 0.2.0 — 2026-06-04

### Features
- **Audit changelog** — field-level diffs appended to `data/_changelog.jsonl` on every scrape. CLI: `malaysia-statutory-rates changelog [--last N]`
- **Validation layer** — range checks, magnitude checks (>30-50% change flags), schema validation. Blocks saves on missing required fields. `--strict` flag blocks on any warning
- **Status command** — data freshness table. CLI: `malaysia-statutory-rates status`. Python API: `rates_status()`
- **Disclaimer** — `DISCLAIMER` constant in package, disclaimer/official_reference in `_metadata` for all new saves. CLI prints disclaimer to stderr
- **Coverage docs** — `COVERAGE.md` documenting foreign worker derivation rules, PCB verification process, state holiday coverage (13 states + 3 FTs), historical rates policy

### CI/CD
- `test.yml` — runs tests on Python 3.10–3.13 + ruff lint (push/PR)
- `scrape.yml` — weekly scheduled scrape (Mon 10am MYT) with `--strict`, creates PR if data changed
- `publish.yml` — publishes to PyPI on merge when data/ or pyproject.toml changes

### Docs
- Versioning strategy documented (hybrid: semver for code, patch bumps for data)
- README updated with all new CLI commands, Python APIs, and CI/CD docs

### Tests
- 328 tests (was 265)
- New: test_changelog.py (16), test_validator.py (14), test_status.py (12), test_disclaimer.py (8), test_e2e.py (18)
- E2E tests cover full pipeline: scrape → validate → changelog → save → status

## 0.1.0 — 2026-05-29

### Data (8 statutory rates)
- EPF contribution rates — 4 categories (citizen <60, citizen ≥60, non-citizen <60, non-citizen ≥60), employer/employee percentages by wage bracket
- SOCSO rates — 65-bracket rate table from PERKESO booklet PDF (Act 4: Employment Injury + Invalidity schemes)
- EIS rates — 65-bracket rate table from PERKESO booklet PDF (Act 800)
- PCB/MTD tax brackets — 10 brackets from LHDN specification PDF, 2 taxpayer categories (single/widowed/divorced vs married)
- PCB tax reliefs — 25 reliefs with 2026 Budget changes
- PCB tax rebates — individual RM400, spouse RM800
- Minimum wage — RM1,700/month, RM8.72/hour (gazette)
- HRDF levy — mandatory 1%, optional 0.5%, exempted industries
- Public holidays — 20 national + 16 individual state groupings (2026)
- Foreign worker rates — EPF + SOCSO (employment injury only) + EIS

### Scrapers
- All scrapers parse live data or raise `ValueError` — no silent fallbacks
- httpx + Firecrawl fallback for blocked sites (KWSP, HRDF Corp)
- robots.txt compliance with Cloudflare challenge detection
- 24-hour HTML/PDF cache, change detection via digest
- PDF parsers: pymupdf for PERKESO booklet (SOCSO/EIS brackets) and LHDN specification (PCB brackets/reliefs/rebates)

### Bug fixes
- PCB scraper: fixed `doc.close()` called before `_extract_bracket_description()` and `_extract_notes()`

### API
- `load_rates()` — load all rates as dict
- `load_rate(name)` — load a single rate
- CLI: `malaysia-statutory-rates show [rate]` and `malaysia-statutory-rates scrape --all`

### Tests
- 265 tests (91% code coverage)
- Data file tests: schema, values, metadata for all 8 JSON files
- Scraper tests: mocked HTTP responses for all 8 scrapers
- Base scraper tests: caching, robots.txt, Firecrawl fallback, change detection
- CLI tests: show, scrape, argument parsing
- PDF parser tests: amount parsing, table extraction from PERKESO booklet
