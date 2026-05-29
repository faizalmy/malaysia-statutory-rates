"""Generate foreign worker rates from existing EPF/SOCSO/EIS data."""

from __future__ import annotations

from datetime import datetime, timezone

from malaysia_statutory_rates.scrapers.base import BaseScraper


class ForeignWorkerScraper(BaseScraper):
    """Combines EPF, SOCSO, and EIS rates for foreign workers.

    Unlike other scrapers, this does NOT fetch from the web.
    It reads from the already-scraped data files and extracts
    foreign-worker-specific rates.
    """

    SOURCE_URL = "Combined — KWSP and PERKESO"
    SOURCE_NAME = "KWSP + PERKESO"

    def scrape(self) -> dict | None:
        from malaysia_statutory_rates.loader import load_rates

        rates = load_rates()
        epf = rates.get("epf_rates", {})
        socso = rates.get("socso_rates", {})
        eis = rates.get("eis_rates", {})

        if not epf:
            return None

        epf_rates = epf.get("rates", {})
        non_my_after = epf_rates.get("non_malaysian_after_aug98", {})
        non_my_before_below = epf_rates.get("malaysian_pr_nonmy_before_aug98_below_60", {})
        non_my_before_60plus = epf_rates.get("pr_nonmy_before_aug98_60_plus", {})

        epf_data = {
            "source": epf.get("source", ""),
            "non_malaysian_after_aug98": {
                "employee": non_my_after.get("employee", {}),
                "employer": non_my_after.get("employer", {}),
                "note": non_my_after.get("note"),
            },
            "non_malaysian_before_aug98_below_60": {
                "employee": non_my_before_below.get("employee", {}),
                "employer": non_my_before_below.get("employer", {}),
                "note": non_my_before_below.get("note"),
            },
            "non_malaysian_before_aug98_60_plus": {
                "employee": non_my_before_60plus.get("employee", {}),
                "employer": non_my_before_60plus.get("employer", {}),
            },
        }

        # SOCSO Employment Injury: employer-only, same rate table as citizens
        socso_rate_table = socso.get("rate_table", [])
        # Get the contribution amount at wage ceiling (last row)
        socso_at_ceiling = socso_rate_table[-1] if socso_rate_table else {}
        socso_wage_ceiling = socso.get("wage_ceiling", 6000)

        socso_data = {
            "source": socso.get("source", ""),
            "employment_injury": {
                "employer_only": socso.get("schemes", {}).get("employment_injury", {}).get("employer_only", True),
                "wage_ceiling": socso_wage_ceiling,
                "contribution_at_ceiling": {
                    "employer": socso_at_ceiling.get("employer_schedule1"),
                    "note": f"RM {socso_at_ceiling.get('employer_schedule1', 'N/A')} per month at RM{socso_wage_ceiling} wage",
                },
                "note": socso.get("schemes", {}).get("employment_injury", {}).get("note"),
            },
            "invalidity": {
                "note": socso.get("schemes", {}).get("invalidity", {}).get("note"),
            },
        }

        # EIS: same rates as citizens (equal employer/employee split)
        eis_rate_table = eis.get("rate_table", [])
        eis_at_ceiling = eis_rate_table[-1] if eis_rate_table else {}
        eis_wage_ceiling = eis.get("wage_ceiling", 6000)

        eis_data = {
            "source": eis.get("source", ""),
            "wage_ceiling": eis_wage_ceiling,
            "contribution_at_ceiling": {
                "employer": eis_at_ceiling.get("employer"),
                "employee": eis_at_ceiling.get("employee"),
                "total": eis_at_ceiling.get("total"),
                "note": f"RM {eis_at_ceiling.get('total', 'N/A')} total per month at RM{eis_wage_ceiling} wage",
            },
            "note": eis.get("description"),
        }

        year = epf.get("year", datetime.now().year)
        effective_from = epf.get("effective_from", "")

        # Build notes from source data
        notes = []
        if effective_from:
            notes.append(f"Foreign worker EPF became mandatory from {effective_from}")
        # Pull notes from SOCSO and EIS data about foreign worker coverage
        seen = set()
        for source_notes in [socso.get("notes", []), eis.get("notes", [])]:
            for note in source_notes:
                if ("foreign" in note.lower() or "employment injury" in note.lower()) and note not in seen:
                    notes.append(note)
                    seen.add(note)

        data = {
            "source": self.SOURCE_URL,
            "year": year,
            "effective_from": effective_from,
            "epf": epf_data,
            "socso": socso_data,
            "eis": eis_data,
            "notes": notes,
        }

        if self.has_changed("foreign_worker_rates.json", data):
            return data
        return None
