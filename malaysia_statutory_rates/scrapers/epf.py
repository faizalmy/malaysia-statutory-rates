"""Scrape EPF contribution rates from KWSP website.

Parses the contribution rate table from the live HTML page.
Extracts: employee/employer rates by wage bracket, Third Schedule PDF link.
"""

import re

from bs4 import BeautifulSoup

from malaysia_statutory_rates.scrapers.base import BaseScraper


class EPFScraper(BaseScraper):
    """Scrape EPF rates from kwsp.gov.my."""

    SOURCE_URL = "https://www.kwsp.gov.my/en/employer/responsibilities/mandatory-contribution"
    SOURCE_NAME = "Kumpulan Wang Simpanan Pekerja (KWSP)"

    def scrape(self) -> dict | None:
        html = self.fetch(self.SOURCE_URL)
        soup = BeautifulSoup(html, "html.parser")

        # Extract Third Schedule PDF link
        third_schedule_url = None
        for a in soup.find_all("a", href=True):
            if "third_schedule" in a["href"].lower():
                href = a["href"]
                third_schedule_url = href if href.startswith("http") else f"https://www.kwsp.gov.my{href}"
                break

        # Parse the contribution rate table
        # Table structure (from live scrape):
        #   Row 1: Malaysian | No limit | '' | Employee 0%, Employer 4%
        #   Row 2: MY/PR/Non-MY(before98) | ≤RM5000 | Employee 11%, Employer 13% | same
        #   Row 3: MY/PR/Non-MY(before98) | >RM5000  | Employee 11%, Employer 12% | PR/Non-MY only: 5.5%/6%
        #   Row 4: Non-MY(from Aug98) | No limit | Employee 2%, Employer 2% | same

        rates = {}

        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            if not any("employee" in h and "status" in h for h in headers):
                continue

            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 4:
                    continue

                status = cols[0].get_text(strip=True, separator=" ")
                salary = cols[1].get_text(strip=True, separator=" ")
                stage1 = cols[2].get_text(strip=True, separator=" ")  # Below 60
                stage2 = cols[3].get_text(strip=True, separator=" ")  # 60+

                # Parse rates from cell text
                s1_emp = self._extract_rate(stage1, "employee")
                s1_er = self._extract_rate(stage1, "employer")
                s2_emp = self._extract_rate(stage2, "employee")
                s2_er = self._extract_rate(stage2, "employer")

                status_lower = status.lower()

                # Row 1: Malaysian, No limit, Stage2 only (60+)
                if "malaysian" in status_lower and "no limit" in salary.lower() and s1_emp is None:
                    if s2_emp is not None:
                        rates["malaysian_60_plus"] = {
                            "label": "Malaysian citizen aged 60 and above",
                            "employee": {"rate": s2_emp, "note": "Optional" if s2_emp == 0 else ""},
                            "employer": {"rate": s2_er},
                        }

                # Row 2: MY/PR/Non-MY(before98), ≤RM5000
                elif "permanent resident" in status_lower and "below" in salary.lower() or \
                     ("5,000" in salary and "below" in salary.lower()):
                    rates["malaysian_pr_nonmy_before_aug98_below_60"] = {
                        "label": "Malaysian / PR / Non-MY registered before 1 Aug 1998 (Below 60)",
                        "employee": {"rate": s1_emp} if s1_emp is not None else {},
                        "employer": {
                            "wage_lte_5000": {"rate": s1_er},
                        },
                    }

                # Row 3: MY/PR/Non-MY(before98), >RM5000
                elif "permanent resident" in status_lower and "more than" in salary.lower() or \
                     ("5,000" in salary and "more than" in salary.lower()):
                    if "malaysian_pr_nonmy_before_aug98_below_60" in rates:
                        rates["malaysian_pr_nonmy_before_aug98_below_60"]["employer"]["wage_gt_5000"] = {"rate": s1_er}
                    # Stage2 for this row: PR and Non-MY(before98) 60+ only
                    if s2_emp is not None and "applicable" in stage2.lower():
                        rates["pr_nonmy_before_aug98_60_plus"] = {
                            "label": "PR / Non-MY registered before 1 Aug 1998 (60+)",
                            "employee": {"rate": s2_emp},
                            "employer": {"rate": s2_er},
                            "note": "Applicable for PR and Non-MY registered before 1 Aug 1998 only",
                        }

                # Row 4: Non-MY(from Aug98), No limit
                elif "non-malaysian" in status_lower and "from" in status_lower and "1998" in status_lower:
                    if s1_emp is not None:
                        rates["non_malaysian_after_aug98"] = {
                            "label": "Non-Malaysian registered from 1 August 1998",
                            "employee": {"rate": s1_emp},
                            "employer": {"rate": s1_er},
                            "note": "No wage limit, any age",
                        }

        if not rates:
            raise ValueError("Could not parse EPF rates from KWSP page")

        # Parse wage components from FAQ
        wage_included, wage_excluded = self._parse_wage_components(soup)

        # Parse notes
        notes = self._parse_notes(soup)

        data = {
            "source": self.SOURCE_URL,
            "year": 2025,
            "effective_from": "2025-10-01",
            "third_schedule_pdf": third_schedule_url,
            "act": "EPF Act 1991 — Section 43(1), Third Schedule",
            "contribution_method": {
                "description": "EPF uses wage range tables for wages up to RM20,000. "
                "For wages above RM20,000, direct percentage applies. "
                "Total contribution rounded up to next ringgit.",
                "source": "kwsp.gov.my — Third Schedule, EPF Act 1991",
            },
            "rates": rates,
            "age_limits": {"min_contribution_age": 14, "max_contribution_age": 75},
            "wage_components": {"included": wage_included, "excluded": wage_excluded},
            "notes": notes,
        }

        if self.has_changed("epf_rates.json", data):
            return data
        return None

    def _extract_rate(self, text: str, party: str) -> float | None:
        """Extract rate percentage from cell text."""
        # Handle both ASCII ' and Unicode ' (U+2019) in "Employer's" / "Employer's"
        pattern = rf"{party}[\u2019']?s?\s*share:\s*(\d+(?:\.\d+)?)\s*%"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1)) / 100
        return None

    def _parse_wage_components(self, soup: BeautifulSoup) -> tuple[list[str], list[str]]:
        """Parse included/excluded wage components from FAQ section."""
        included = []
        excluded = []

        # Find "Components of Wage" heading
        for heading in soup.find_all(["h3", "h4"]):
            text = heading.get_text(strip=True).lower()
            if "component" in text and "wage" in text:
                sibling = heading.find_next_sibling()
                if sibling:
                    for li in sibling.find_all("li"):
                        item = li.get_text(strip=True)
                        # Clean up numbered items
                        item = re.sub(r"^\d+\.\s*", "", item)
                        if item:
                            included.append(item)

            # Find "Non-Wages" section
            if "non-wage" in text or "non wage" in text:
                sibling = heading.find_next_sibling()
                if sibling:
                    for li in sibling.find_all("li"):
                        excluded.append(li.get_text(strip=True))

        return included, excluded

    def _parse_notes(self, soup: BeautifulSoup) -> list[str]:
        """Parse important notes from the page."""
        notes = []
        full_text = soup.get_text()

        # Look for numbered notes near the rate table
        for match in re.finditer(r"(\d)\\\.\s*(.+?)(?=\d\\\.|$)", full_text):
            note = match.group(2).strip()
            if len(note) > 10 and any(kw in note.lower() for kw in ["effective", "minimum age", "rounded", "october"]):
                notes.append(note)

        if not notes:
            notes = [
                "Effective October 2025 salary/wage",
                "Third Schedule PDF contains full wage range lookup tables",
                "Wages above RM20,000 use percentage; up to RM20,000 use wage range table",
            ]

        return notes
