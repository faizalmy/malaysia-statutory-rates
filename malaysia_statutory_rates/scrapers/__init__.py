"""Scrapers for Malaysian statutory rates."""

from malaysia_statutory_rates.scrapers.eis import EISScraper
from malaysia_statutory_rates.scrapers.epf import EPFScraper
from malaysia_statutory_rates.scrapers.foreign_worker import ForeignWorkerScraper
from malaysia_statutory_rates.scrapers.holidays import HolidaysScraper
from malaysia_statutory_rates.scrapers.hrdf import HRDFScraper
from malaysia_statutory_rates.scrapers.minimum_wage import MinimumWageScraper
from malaysia_statutory_rates.scrapers.socso import SOCSOScraper

SCRAPERS: dict[str, type] = {
    "minimum_wage": MinimumWageScraper,
    "hrdf_rates": HRDFScraper,
    "epf_rates": EPFScraper,
    "socso_rates": SOCSOScraper,
    "eis_rates": EISScraper,
    "foreign_worker_rates": ForeignWorkerScraper,
    "public_holidays": HolidaysScraper,
}


def run_scrapers(targets: list[str] | None = None) -> dict[str, bool]:
    """Run scrapers. Returns {name: changed}."""
    results = {}
    to_run = targets or list(SCRAPERS.keys())

    for name in to_run:
        if name not in SCRAPERS:
            print(f"  WARNING: Unknown scraper '{name}', skipping")
            continue
        scraper = SCRAPERS[name]()
        try:
            data = scraper.scrape()
            if data is not None:
                scraper.save(f"{name}.json", data)
                results[name] = True
            else:
                results[name] = False
        except Exception as e:
            results[name] = False
            print(f"  {name}: ERROR — {e}")

    return results
