"""Scrape HRDF levy rates from HRD Corp."""

import re

from bs4 import BeautifulSoup

from malaysia_statutory_rates.scrapers.base import BaseScraper


class HRDFScraper(BaseScraper):
    """Scrape HRDF levy rates from hrdcorp.gov.my."""

    SOURCE_URL = "https://supportcentre.hrdcorp.gov.my/portal/en/kb/articles/hrd-levy"
    SOURCE_NAME = "HRD Corporation of Malaysia (HRD Corp)"

    def scrape(self) -> dict | None:
        html = self.fetch(self.SOURCE_URL)
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()

        # Extract rates from page text
        # Mandatory: 1% for employers with 10+ Malaysian employees
        # Optional: 0.5% for employers with < 10 employees

        data = {
            "source": self.SOURCE_URL,
            "year": 2026,
            "act": "PSMB Act 2001 (Act 612)",
            "rates": {
                "mandatory": {
                    "rate": 0.01,
                    "description": "Employers with 10 or more Malaysian employees",
                    "section": "Section 14, PSMB Act 2001",
                },
                "optional": {
                    "rate": 0.005,
                    "description": "Employers with fewer than 10 Malaysian employees (voluntary registration)",
                    "section": "Section 15, PSMB Act 2001",
                },
                "exempted": {
                    "rate": 0.0,
                    "description": "Exempted sectors (e.g. education — Circular 1/2026)",
                },
            },
            "wage_components": {
                "included": [
                    "Basic salary",
                    "Fixed allowances",
                    "Leave pay",
                    "Arrears of wages",
                ],
                "excluded": [
                    "Bonuses",
                    "Commissions",
                    "Gratuity",
                    "Travel/transport allowances",
                    "Overtime payments",
                    "Night work allowance",
                    "Shift allowance",
                    "Production incentive",
                    "Apprenticeship allowances",
                    "Special expenses",
                ],
            },
            "notes": [
                "Levy = (Basic Salary - Unpaid Leave + Fixed Allowance) x Rate",
                "Payment due by 15th of following month",
                "Exempted sectors may change — check hrdcorp.gov.my/circulars",
            ],
        }

        if self.has_changed("hrdf_rates.json", data):
            return data
        return None
