"""Scrapers for Malaysian statutory rates.

Imports are lazy so the core package can be used without scraper
extras (pymupdf, httpx, etc.) installed.
"""

from typing import Any

__all__ = ["SCRAPERS", "run_scrapers"]


def _load_scraper_classes() -> dict[str, Any]:
    """Import scraper classes on first access (avoids hard dep on pymupdf etc.)."""
    from malaysia_statutory_rates.scrapers.eis import EISScraper
    from malaysia_statutory_rates.scrapers.epf import EPFScraper
    from malaysia_statutory_rates.scrapers.foreign_worker import ForeignWorkerScraper
    from malaysia_statutory_rates.scrapers.holidays import HolidaysScraper
    from malaysia_statutory_rates.scrapers.hrdf import HRDFScraper
    from malaysia_statutory_rates.scrapers.minimum_wage import MinimumWageScraper
    from malaysia_statutory_rates.scrapers.pcb import PCBScraper
    from malaysia_statutory_rates.scrapers.socso import SOCSOScraper

    return {
        "minimum_wage": MinimumWageScraper,
        "hrdf_rates": HRDFScraper,
        "epf_rates": EPFScraper,
        "socso_rates": SOCSOScraper,
        "eis_rates": EISScraper,
        "pcb_table": PCBScraper,
        "foreign_worker_rates": ForeignWorkerScraper,
        "public_holidays": HolidaysScraper,
    }


class _ScraperRegistry:
    """Lazy dict-like registry — imports only happen on first access."""

    def __init__(self) -> None:
        self._data: dict[str, Any] | None = None

    def _ensure(self) -> dict[str, Any]:
        if self._data is None:
            self._data = _load_scraper_classes()
        return self._data

    def __getitem__(self, key: str) -> Any:
        return self._ensure()[key]

    def __iter__(self) -> Any:
        return iter(self._ensure())

    def __len__(self) -> int:
        return len(self._ensure())

    def __contains__(self, key: object) -> bool:
        return key in self._ensure()

    def keys(self) -> Any:
        return self._ensure().keys()

    def values(self) -> Any:
        return self._ensure().values()

    def items(self) -> Any:
        return self._ensure().items()


SCRAPERS = _ScraperRegistry()


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
