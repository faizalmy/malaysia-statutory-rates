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
                "note": non_my_after.get("note", "Non-Malaysian registered from 1 August 1998"),
            },
            "non_malaysian_before_aug98_below_60": {
                "employee": non_my_before_below.get("employee", {}),
                "employer": non_my_before_below.get("employer", {}),
                "note": "Same as Malaysian citizen rates",
            },
            "non_malaysian_before_aug98_60_plus": {
                "employee": non_my_before_60plus.get("employee", {}),
                "employer": non_my_before_60plus.get("employer", {}),
            },
        }

        socso_data = {
            "source": socso.get("source", ""),
            "employment_injury": {
                "employer_only": socso.get("schemes", {}).get("employment_injury", {}).get("employer_only", True),
                "note": "Foreign workers — Employment Injury scheme only. Rate in Act 4 PDF.",
            },
            "invalidity": {
                "note": "Foreign workers are NOT covered under the Invalidity scheme",
            },
        }

        eis_data = {
            "source": eis.get("source", ""),
            "note": "Foreign workers are covered under EIS at the same rate as citizens",
        }

        year = epf.get("year", datetime.now().year)
        effective_from = epf.get("effective_from", "")

        data = {
            "source": self.SOURCE_URL,
            "year": year,
            "effective_from": effective_from,
            "description": "EPF, SOCSO, and EIS contribution rates for foreign workers in Malaysia",
            "epf": epf_data,
            "socso": socso_data,
            "eis": eis_data,
            "notes": [
                f"Foreign worker EPF became mandatory from {effective_from}" if effective_from else "Foreign worker EPF is mandatory",
                "SOCSO coverage for foreign workers is Employment Injury only (no Invalidity)",
                "EIS coverage is the same as Malaysian workers",
                "Domestic workers have different eligibility — check PERKESO guidelines",
            ],
        }

        if self.has_changed("foreign_worker_rates.json", data):
            return data
        return None
