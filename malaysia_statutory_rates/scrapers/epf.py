"""Scrape EPF contribution rates from KWSP website.

Parses the contribution rate table from the live HTML page.
Extracts: employee/employer rates by wage bracket, Third Schedule PDF link.
"""

import re
from datetime import datetime

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
                stage1 = cols[2].get_text(strip=True, separator=" ")
                stage2 = cols[3].get_text(strip=True, separator=" ")

                s1_emp = self._extract_rate(stage1, "employee")
                s1_er = self._extract_rate(stage1, "employer")
                s2_emp = self._extract_rate(stage2, "employee")
                s2_er = self._extract_rate(stage2, "employer")

                status_lower = status.lower()

                # Row 1: Malaysian, No limit, Stage2 only (60+)
                if "malaysian" in status_lower and "no limit" in salary.lower() and s1_emp is None:
                    if s2_emp is not None:
                        rates["malaysian_60_plus"] = {
                            "label": status,
                            "salary_range": salary,
                            "employee": {"rate": s2_emp, "note": "Optional" if s2_emp == 0 else ""},
                            "employer": {"rate": s2_er},
                        }

                # Row 2: MY/PR/Non-MY(before98), ≤RM5000
                elif "permanent resident" in status_lower and "below" in salary.lower() or \
                     ("5,000" in salary and "below" in salary.lower()):
                    rates["malaysian_pr_nonmy_before_aug98_below_60"] = {
                        "label": status,
                        "salary_range": salary,
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
                    if s2_emp is not None and "applicable" in stage2.lower():
                        # Extract the "Applicable for (ii) and (iii) only" text from the cell
                        applicable_match = re.search(r"(applicable[^.]*)", stage2, re.IGNORECASE)
                        note_text = applicable_match.group(1).strip() if applicable_match else stage2
                        rates["pr_nonmy_before_aug98_60_plus"] = {
                            "label": status,
                            "salary_range": salary,
                            "employee": {"rate": s2_emp},
                            "employer": {"rate": s2_er},
                            "note": note_text,
                        }

                # Row 4: Non-MY(from Aug98), No limit
                elif "non-malaysian" in status_lower and "from" in status_lower and "1998" in status_lower:
                    if s1_emp is not None:
                        rates["non_malaysian_after_aug98"] = {
                            "label": status,
                            "salary_range": salary,
                            "employee": {"rate": s1_emp},
                            "employer": {"rate": s1_er},
                        }

        if not rates:
            raise ValueError("Could not parse EPF rates from KWSP page")

        # Parse wage components from FAQ
        wage_included, wage_excluded = self._parse_wage_components(soup)

        # Parse Third Schedule bracket table
        bracket_table = self._parse_third_schedule(third_schedule_url)

        # Parse notes
        notes = self._parse_notes(soup)

        # Extract metadata from page text
        full_text = soup.get_text()
        year = self._extract_year(full_text)
        effective_from = self._extract_effective_from(full_text)
        act = self._extract_act(full_text)
        age_limits = self._extract_age_limits(full_text)

        # Parse contribution method from page
        contribution_method = self._parse_contribution_method(full_text)

        data = {
            "source": self.SOURCE_URL,
            "year": year,
            "effective_from": effective_from,
            "third_schedule_pdf": third_schedule_url,
            "act": act,
            "contribution_method": contribution_method,
            "rates": rates,
            "age_limits": age_limits,
            "wage_components": {"included": wage_included, "excluded": wage_excluded},
            "wage_bracket_table": bracket_table,
            "notes": notes,
        }

        if self.has_changed("epf_rates.json", data):
            return data
        return None

    def _extract_rate(self, text: str, party: str) -> float | None:
        """Extract rate percentage from cell text."""
        pattern = rf"{party}[\u2019']?s?\s*share:\s*(\d+(?:\.\d+)?)\s*%"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1)) / 100
        return None

    def _extract_year(self, text: str) -> int:
        """Extract year from page text. Raises ValueError if not found."""
        match = re.search(r"(?:effective\s+\d{1,2}\s+\w+\s+|october\s+|salary/wage\s+)(\d{4})", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r"(?:effective|october).*?(\d{4})", text, re.IGNORECASE | re.DOTALL)
        if match:
            return int(match.group(1))
        raise ValueError("Could not extract year from EPF page")

    def _extract_effective_from(self, text: str) -> str:
        """Extract effective date and convert to ISO format. Raises ValueError if not found."""
        match = re.search(r"effective\s+(?:for\s+)?(\d{1,2})\s+(\w+)\s+(\d{4})", text, re.IGNORECASE)
        if match:
            day, month_name, year = match.group(1), match.group(2), match.group(3)
            try:
                dt = datetime.strptime(f"{day} {month_name} {year}", "%d %B %Y")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        match = re.search(r"effective\s+(?:for\s+)?(\w+)\s+(\d{4})", text, re.IGNORECASE)
        if match:
            month_name, year = match.group(1), match.group(2)
            try:
                dt = datetime.strptime(f"1 {month_name} {year}", "%d %B %Y")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        raise ValueError("Could not extract effective date from EPF page")

    def _extract_act(self, text: str) -> str:
        """Extract act reference from page text. Raises ValueError if not found."""
        act_match = re.search(r"(?:employees?\s+provident\s+fund\s+)?(?:EPF\s+)?Act\s+(\d{4})", text, re.IGNORECASE)
        section_match = re.search(r"Section\s+(\d+\(\d+\))", text, re.IGNORECASE)
        if act_match:
            act_year = act_match.group(1)
            act_str = f"EPF Act {act_year}"
            if section_match:
                act_str += f" — Section {section_match.group(1)}, Third Schedule"
            else:
                act_str += ", Third Schedule"
            return act_str
        raise ValueError("Could not extract act reference from EPF page")

    def _extract_age_limits(self, text: str) -> dict:
        """Extract min/max contribution ages from page text. Raises ValueError if not found."""
        min_age = None
        max_age = None
        min_match = re.search(r"minimum\s+age.*?(?:is\s+age\s+|of\s+)(\d{1,2})", text, re.IGNORECASE | re.DOTALL)
        if min_match:
            min_age = int(min_match.group(1))
        max_match = re.search(r"maximum\s+age.*?(?:is\s+|of\s+)(\d{1,2})\s*(?:years?\s*old)?", text, re.IGNORECASE | re.DOTALL)
        if max_match:
            max_age = int(max_match.group(1))
        if min_age is None or max_age is None:
            raise ValueError("Could not extract age limits from EPF page")
        return {"min_contribution_age": min_age, "max_contribution_age": max_age}

    def _parse_wage_components(self, soup: BeautifulSoup) -> tuple[list[str], list[str]]:
        """Parse included/excluded wage components from FAQ section. Returns empty lists if not found."""
        included = []
        excluded = []

        full_text = soup.get_text(separator="\n")

        # Extract included wage components from FAQ #8
        # Pattern: numbered list after "Components of Wage"
        components_match = re.search(
            r"Payments\s+which\s+are\s+subject\s+to\s+EPF\s+contribution\s+include:\s*(.*?)(?=\d+\.\s+What\s+is\s+the\s+definition|Non[- ]?Wage|not\s+liable\s+for\s+EPF|$)",
            full_text, re.DOTALL | re.IGNORECASE
        )
        if components_match:
            block = components_match.group(1)
            items = [x.strip() for x in block.split("\n") if x.strip()]
            included.extend(items)

        # Extract excluded non-wage components from FAQ #11
        nonwage_match = re.search(
            r"Payments\s+which\s+are\s+not\s+liable\s+for\s+EPF\s+contribution\s+are:\s*(.*?)(?=\d+\.\s+Who\s+are\s+EPF|The\s+above\s+list|Third\s+Schedule|$)",
            full_text, re.DOTALL | re.IGNORECASE
        )
        if nonwage_match:
            block = nonwage_match.group(1)
            # Items may be concatenated (e.g. "Service chargeOvertime payment")
            # Split on lowercase→uppercase boundary
            items_text = re.sub(r"([a-z])([A-Z])", r"\1\n\2", block)
            for item_match in re.finditer(r"([A-Z][^\n]+?)(?:\n|$)", items_text):
                item = item_match.group(1).strip()
                item = re.sub(r"\.$", "", item)  # trailing period
                if item and len(item) > 3:
                    excluded.append(item)

        return included, excluded

    def _parse_contribution_method(self, text: str) -> dict:
        """Parse contribution method details from page text. Raises ValueError if not found."""
        # Extract the key sentence about wage range vs percentage
        description_parts = []

        # Look for the specific sentence about percentage calculation
        range_match = re.search(
            r"(not allowed to calculate[^.]*percentage[^.]*EXCEPT[^.]*exceed[^.]*RM[\d,]+[^.]*\.)",
            text, re.IGNORECASE,
        )
        if range_match:
            desc = range_match.group(1).strip()
            desc = re.sub(r"\s+", " ", desc)
            description_parts.append(desc)

        # Look for rounding rule
        round_match = re.search(
            r"(total contribution[^.]*rounded[^.]*ringgit[^.]*\.)",
            text, re.IGNORECASE,
        )
        if round_match:
            desc = round_match.group(1).strip()
            desc = re.sub(r"\s+", " ", desc)
            if desc not in " ".join(description_parts):
                description_parts.append(desc)

        if not description_parts:
            raise ValueError("Could not extract contribution method description from EPF page")

        # Extract source reference
        source = "Third Schedule, EPF Act 1991"
        act_ref = re.search(r"(EPF Act \d{4})", text, re.IGNORECASE)
        if act_ref:
            act_year = act_ref.group(1)
            source = f"Third Schedule, {act_year}"

        return {
            "description": " ".join(description_parts),
            "source": source,
        }

    def _parse_notes(self, soup: BeautifulSoup) -> list[str]:
        """Parse important notes from the page. Returns empty list if none found."""
        notes = []
        full_text = soup.get_text()

        # Effective date note
        effective_match = re.search(r"(Effective\s+for\s+\w+\s+\d{4}\s+salary/wage\s*\([^)]*\))", full_text, re.IGNORECASE)
        if effective_match:
            note = effective_match.group(1).strip()
            note = re.sub(r"\s+", " ", note)
            if len(note) > 10:
                notes.append(note)

        # Age limits note
        age_match = re.search(r"(minimum age[^.]*\d+[^.]*maximum age[^.]*\d+[^.]*years? old[^.]*\.)", full_text, re.IGNORECASE)
        if age_match:
            note = age_match.group(1).strip()
            note = re.sub(r"\s+", " ", note)
            notes.append(note)

        # Rounding note
        rounding_match = re.search(r"(total contribution[^.]*rounded[^.]*ringgit[^.]*\.)", full_text, re.IGNORECASE)
        if rounding_match:
            note = rounding_match.group(1).strip()
            note = re.sub(r"\s+", " ", note)
            if note not in notes:
                notes.append(note)

        # Payment deadline
        deadline_match = re.search(r"(Employer must make monthly payment on or before \d+\w+ of the month)", full_text, re.IGNORECASE)
        if deadline_match:
            note = deadline_match.group(1).strip()
            note = re.sub(r"\s+", " ", note)
            if note not in notes:
                notes.append(note)

        return notes

    def _parse_third_schedule(self, url: str | None) -> dict:
        """Parse Third Schedule PDF via Firecrawl and extract bracket tables.

        Returns dict with keys: part_a, part_c, part_e, part_f
        Each part has a list of bracket dicts with wage_min, wage_max, employer, employee, total.
        """
        if not url:
            return {}

        try:
            md = self._fetch_firecrawl_markdown(url)
        except Exception as e:
            print(f"    WARNING: Could not fetch Third Schedule PDF: {e}")
            return {}

        if not md:
            return {}

        parts = {}
        # Split by PART sections — flexible regex to catch Parts B and D regardless of formatting
        # Handles: bare "PART B", bold "**PART B**", separators, case insensitive
        part_sections = re.split(
            r"(?:^|\n)\s*(?:\*\*\*)?\s*PART\s+([A-F])\s*(?:\*\*\*)?",
            md, flags=re.IGNORECASE | re.MULTILINE
        )

        for i in range(1, len(part_sections), 2):
            part_letter = part_sections[i].strip()
            part_text = part_sections[i + 1] if i + 1 < len(part_sections) else ""
            brackets = self._extract_bracket_rows(part_text)
            if brackets:
                # Determine rate_type based on bracket structure
                has_fixed = any(
                    "employer" in b and isinstance(b.get("employer"), (int, float))
                    for b in brackets
                )
                has_percentage = any("employer_rate" in b for b in brackets)
                rate_type = "flat" if (has_percentage and not has_fixed) else "bracket"
                parts[f"part_{part_letter.lower()}"] = {
                    "description": self._extract_part_description(part_text, part_letter),
                    "brackets": brackets,
                    "rate_type": rate_type,
                }

        return parts

    def _extract_bracket_rows(self, text: str) -> list[dict]:
        """Extract bracket rows from a Third Schedule part's markdown table."""
        brackets = []
        # Match rows like: | From | 220.01 | to | 240.00 | 32.00 | 27.00 | 59.00 |
        row_pattern = r"\|\s*From\s*\|\s*([\d,]+\.\d+)\s*\|\s*to\s*\|\s*([\d,]+\.\d+)\s*\|\s*([\d,]+\.\d+|NIL)\s*\|\s*([\d,]+\.\d+|NIL)\s*\|\s*([\d,]+\.\d+|NIL)\s*\|"
        for match in re.finditer(row_pattern, text):
            wage_min = float(match.group(1).replace(",", ""))
            wage_max = float(match.group(2).replace(",", ""))
            employer = 0.0 if match.group(3) == "NIL" else float(match.group(3).replace(",", ""))
            employee = 0.0 if match.group(4) == "NIL" else float(match.group(4).replace(",", ""))
            total = 0.0 if match.group(5) == "NIL" else float(match.group(5).replace(",", ""))
            brackets.append({
                "wage_min": wage_min,
                "wage_max": wage_max,
                "employer": employer,
                "employee": employee,
                "total": total,
            })

        # Issue 11: validate bracket continuity — fill gaps by extending wage_max
        for i in range(len(brackets) - 1):
            if brackets[i].get('wage_max') is not None and brackets[i + 1].get('wage_min') is not None:
                expected_min = round(brackets[i]['wage_max'] + 0.01, 2)
                if brackets[i + 1]['wage_min'] > expected_min:
                    # Gap detected — extend previous bracket's max to bridge the gap
                    brackets[i]['wage_max'] = round(brackets[i + 1]['wage_min'] - 0.01, 2)

        # Match the "exceed RM20,000" percentage rule (the actual rule, not the Note)
        # Look for the specific pattern: "contribution by the employee...X%...employer...Y%"
        exceed_match = re.search(
            r"exceed\s+RM([\d,]+\.?\d*).*?contribution\s+by\s+the\s+employee.*?(\d+(?:\.\d+)?%).*?contribution\s+by\s+the\s+employer.*?(\d+(?:\.\d+)?%)",
            text, re.IGNORECASE | re.DOTALL
        )
        if not exceed_match:
            # Try employer first
            exceed_match = re.search(
                r"exceed\s+RM([\d,]+\.?\d*).*?contribution\s+by\s+the\s+employer.*?(\d+(?:\.\d+)?%).*?contribution\s+by\s+the\s+employee.*?(\d+(?:\.\d+)?%)",
                text, re.IGNORECASE | re.DOTALL
            )
            if exceed_match:
                brackets.append({
                    "wage_min": float(exceed_match.group(1).replace(",", "")),
                    "wage_max": None,
                    "employer_rate": float(exceed_match.group(2).replace("%", "")) / 100,
                    "employee_rate": float(exceed_match.group(3).replace("%", "")) / 100,
                    "note": "Percentage-based for wages exceeding this amount",
                })
        else:
            brackets.append({
                "wage_min": float(exceed_match.group(1).replace(",", "")),
                "wage_max": None,
                "employer_rate": float(exceed_match.group(3).replace("%", "")) / 100,
                "employee_rate": float(exceed_match.group(2).replace("%", "")) / 100,
                "note": "Percentage-based for wages exceeding this amount",
            })

        # Match flat percentage rate (Part F style: "2% of the amount of wages")
        # Issue 10: normalize to use same field names as bracket parts (employer/employee/total)
        if not brackets:
            flat_match = re.search(
                r"(\d+(?:\.\d+)?%)\s+of\s+the\s+amount\s+of\s+wages",
                text, re.IGNORECASE
            )
            if flat_match:
                # Find all occurrences (employer listed first, then employee in typical PDF)
                all_flats = re.findall(r"(\d+(?:\.\d+)?)%\s+of\s+the\s+amount\s+of\s+wages", text, re.IGNORECASE)
                if len(all_flats) >= 2:
                    emp_pct = float(all_flats[0])
                    er_pct = float(all_flats[1])
                    brackets.append({
                        "wage_min": 0,
                        "wage_max": None,
                        "employer": f"{all_flats[0]}%",
                        "employee": f"{all_flats[1]}%",
                        "total": f"{emp_pct + er_pct:.0f}%",
                        "employer_rate": emp_pct / 100,
                        "employee_rate": er_pct / 100,
                        "note": "Flat rate for all wages",
                    })

        return brackets

    def _extract_part_description(self, text: str, part_letter: str) -> str:
        """Extract the description text for a Third Schedule part."""
        desc_match = re.search(
            r"(\d+\.\s+The\s+rate\s+of\s+monthly\s+contributions[^.]*(?:\.[^.]){0,3})",
            text, re.IGNORECASE
        )
        if desc_match:
            return re.sub(r"\s+", " ", desc_match.group(1).strip())
        return f"Part {part_letter}"
