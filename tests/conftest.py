"""Shared test fixtures for malaysia-statutory-rates."""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary data directory."""
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Create a temporary cache directory."""
    d = tmp_path / "cache"
    d.mkdir()
    return d


# --- Sample HTML fixtures ---

PERKESO_HTML = """
<html><body>
<h2>Update on Contribution Amount for Act 4 and Act 800 in accordance with the Increment of the Wage Ceiling Limit Effective 1 October 2024, PERKESO will enforce a new wage ceiling for contributions from RM5,000 to RM6,000 per month. The contribution amount that apply to employees with salaries exceeding the ceiling shall be based on the ceiling amount.</h2>
<h3>Contribution Rate of Act 4</h3>
<h3>Contribution Rate of Act 800</h3>
<h3>Rate of Contribution Self-Employment Social Security Scheme(Act 789)</h3>
<h3>Rate of Contribution Housewives' Social Security Scheme (Act 838) A contribution of RM120 shall be paid in advance, covering a period of 12 consecutive months.</h3>
<p>The contribution rates for Foreign Workers are refer to the Third Schedule (Act 4), whereas Domestic Workers' contribution rates are based on eligibility criteria listed in the Domestic Worker section</p>
<p>0.4% Employment Insurance System contribution rate applies equally to both employer and employee. Both employer and employee contribute equally.</p>
<table>
<tr><td>1</td><td>RM1,000</td><td>RM5.30</td></tr>
<tr><td>2</td><td>RM2,000</td><td>RM10.60</td></tr>
</table>
<a href="/images/dokumen/risalah/ACT4.pdf">Act 4 PDF</a>
<a href="/images/dokumen/risalah/ACT800.pdf">Act 800 PDF</a>
</body></html>
"""

KWSP_HTML = """
<html><body>
<h1>Employer's Responsibility - Mandatory Contribution</h1>
<p>Effective for October 2025 salary/wage (year of assessment 2025)</p>
<p>Under the EPF Act 1991, Section 43(2), the contribution rates are based on the Third Schedule.</p>
<p>The minimum age for mandatory contribution is age 16 and the maximum age is 75 years old.</p>
<table>
<tr><th>Employee Status</th><th>Salary Range</th><th>Stage 1 (current)</th><th>Stage 2 (optional for 60+)</th></tr>
<tr>
<td>Malaysian / Permanent Resident / Non-Malaysian registered before 1 August 1998</td>
<td>Below RM5,000</td>
<td>Employee's share: 11% Employer's share: 13%</td>
<td>Not applicable</td>
</tr>
<tr>
<td>Malaysian / Permanent Resident / Non-Malaysian registered before 1 August 1998</td>
<td>More than RM5,000</td>
<td>Employee's share: 11% Employer's share: 12%</td>
<td>Not applicable</td>
</tr>
<tr>
<td>Malaysian aged 60 and above</td>
<td>No limit</td>
<td>Not applicable</td>
<td>Employee's share: 0% Employer's share: 4%</td>
</tr>
<tr>
<td>Non-Malaysian registered from 1 August 1998</td>
<td>No limit</td>
<td>Employee's share: 11% Employer's share: 2%</td>
<td>Not applicable</td>
</tr>
</table>
<h3>Wage Components</h3>
<ul><li>Basic salary</li><li>Fixed allowance</li></ul>
<h3>Non-Wage Components</h3>
<ul><li>Overtime</li><li>Annual bonus</li></ul>
<a href="/third_schedule.pdf">Third Schedule PDF</a>
<p>Employers are not allowed to calculate contributions based on percentage EXCEPT when wages exceed RM20,000. Rounded to next ringgit.</p>
<p>Total contribution rounded up to next ringgit.</p>
</body></html>
"""

MOHR_HTML = """
<html><body>
<h1>Portal Gaji Minimum</h1>
<div>RM1700Kadar Gaji MinimumBulanan</div>
<div>RM8.72Kadar Gaji MinimumSetiap Jam</div>
<a href="https://gajiminimum.mohr.gov.my/PUA%20376.pdf">Warta Perintah Gaji Minimum 2024</a>
</body></html>
"""

HRDF_HTML = """
<html><body>
<h1>HRD Levy</h1>
<p>PSMB Act 2001 (Act 612) — Human Resources Development Fund</p>
<p>Section 14 of the PSMB Act 2001: Every employer who employs 10 or more Malaysian employees shall be subject to HRDF levy at 1% of the monthly wage(s).</p>
<p>Section 15 of the PSMB Act 2001: Employers with fewer than 10 Malaysian employees may voluntarily register and pay 0.5% of the monthly wage(s).</p>
<p>WagesBasic salary and fixed allowance and includes any leave pay and arrears of wages but DOES NOT INCLUDE: -any pension fund -any retrenchment benefit -any gratuity</p>
<p>Example of wages Exempted: commissions-Gratuity-Overtime pay</p>
<p>Example of non-fixed allowance Exempted: travelling allowance-Shift allowance</p>
<p>LEVY = [(BASIC SALARY - UNPAID LEAVE) + FIXED ALLOWANCE] x 1%</p>
<p>Payment is due within 15 days of the following month.</p>
</body></html>
"""

HOLIDAYS_HTML = """
<html><body>
<h2>2026 Public Holidays in Malaysia</h2>
<table>
<tr><th>Date</th><th>Holiday</th><th>States</th></tr>
<tr><td>1 Jan</td><td>Wed</td><td>New Year's Day</td><td>National</td></tr>
<tr><td>29 Jan</td><td>Wed</td><td>Chinese New Year</td><td>National</td></tr>
<tr><td>1 Feb</td><td>Sat</td><td>Federal Territory Day</td><td>Kuala Lumpur, Labuan, Putrajaya</td></tr>
<tr><td>5 Feb</td><td>Wed</td><td>Thaipusam</td><td>Johor, Kedah, Kuala Lumpur, Negeri Sembilan, Penang, Perak, Putrajaya, Selangor</td></tr>
</table>
</body></html>
"""

EPF_RATES_JSON = {
    "source": "https://www.kwsp.gov.my/en/employer/responsibilities/mandatory-contribution",
    "year": 2025,
    "effective_from": "2025-10-01",
    "third_schedule_pdf": "https://www.kwsp.gov.my/third_schedule.pdf",
    "act": "EPF Act 1991 — Section 43(2), Third Schedule",
    "contribution_method": {"description": "test"},
    "rates": {
        "non_malaysian_after_aug98": {
            "label": "Non-Malaysian registered from 1 August 1998",
            "employee": {"rate": 0.11},
            "employer": {"rate": 0.02},
            "note": "No wage limit, any age",
        },
        "malaysian_pr_nonmy_before_aug98_below_60": {
            "label": "MY/PR/Non-MY before Aug98 below 60",
            "employee": {"rate": 0.11},
            "employer": {"wage_lte_5000": {"rate": 0.13}, "wage_gt_5000": {"rate": 0.12}},
        },
    },
    "age_limits": {"min_contribution_age": 16, "max_contribution_age": 75},
    "wage_components": {"included": ["Basic salary"], "excluded": ["Overtime"]},
    "notes": ["test note"],
}

SOCSO_RATES_JSON = {
    "source": "https://www.perkeso.gov.my/en/rate-of-contribution.html",
    "act": "Employees Social Security Act 1969 (Act 4)",
    "year": 2024,
    "effective_from": "2024-10-01",
    "wage_ceiling": 6000,
    "pdf_url": "https://www.perkeso.gov.my/images/dokumen/risalah/ACT_4.pdf",
    "announcement": "test",
    "schemes": {
        "employment_injury": {"full_name": "Employment Injury Scheme", "employer_only": True, "note": "test"},
        "invalidity": {"full_name": "Invalidity Scheme", "note": "test"},
    },
    "self_employment_scheme": {"act": "Act 789", "rates": []},
    "housewives_scheme": {"act": "Act 838", "contribution": "RM120 per year"},
    "rate_table": [{"row": 1, "wage_min": 0, "wage_max": 100, "employer_schedule1": 0.4, "employee_schedule1": 0.0, "total_schedule1": 0.4, "total_schedule2": 0.2}],
    "notes": ["test"],
}

EIS_RATES_JSON = {
    "source": "https://www.perkeso.gov.my/en/rate-of-contribution.html",
    "act": "Employment Insurance System Act 2017 (Act 800)",
    "year": 2024,
    "effective_from": "2024-10-01",
    "wage_ceiling": 6000,
    "pdf_url": "https://www.perkeso.gov.my/images/dokumen/risalah/ACT_800.pdf",
    "description": "test",
    "rate_table": [{"row": 1, "wage_min": 0, "wage_max": 100, "employer": 0.2, "employee": 0.2, "total": 0.4}],
    "notes": ["test"],
}


# --- Fixtures for scraper tests ---

@pytest.fixture
def socso_html():
    return PERKESO_HTML


@pytest.fixture
def eis_html():
    return PERKESO_HTML


@pytest.fixture
def epf_html():
    return KWSP_HTML


@pytest.fixture
def minimum_wage_html():
    return MOHR_HTML


@pytest.fixture
def minimum_wage_html_alt():
    return """<html><body>
<div>RM1,700Kadar Gaji MinimumBulanan</div>
<div>RM8.72Kadar Gaji MinimumSetiap Jam</div>
<a href="https://gajiminimum.mohr.gov.my/PUA%20376.pdf">Warta Perintah Gaji Minimum 2024</a>
</body></html>"""


@pytest.fixture
def hrdf_html():
    return HRDF_HTML


@pytest.fixture
def holidays_html():
    return HOLIDAYS_HTML
