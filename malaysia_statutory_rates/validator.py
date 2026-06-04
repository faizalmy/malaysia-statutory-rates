"""Validation layer for scraped statutory rate data.

Runs after scraping, before saving. Catches:
- Range violations (rate outside expected bounds)
- Magnitude changes (rate jumped too much since last scrape)
- Schema issues (missing fields, wrong types)
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationError:
    """A single validation issue."""

    scraper: str
    path: str
    rule: str
    message: str
    severity: str = "warning"  # "warning" or "error"

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.scraper}/{self.path}: {self.message}"


# ── Validation rules ──────────────────────────────────────────────────────────

RANGE_RULES: dict[str, dict[str, dict[str, float]]] = {
    "epf_rates": {
        # Top-level rates (malaysian_pr_nonmy_before_aug98_below_60)
        "rates.malaysian_pr_nonmy_before_aug98_below_60.employee.rate": {"min": 0.08, "max": 0.13},
        "rates.malaysian_pr_nonmy_before_aug98_below_60.employer.wage_lte_5000.rate": {"min": 0.09, "max": 0.15},
        "rates.malaysian_pr_nonmy_before_aug98_below_60.employer.wage_gt_5000.rate": {"min": 0.09, "max": 0.15},
        "rates.malaysian_60_plus.employee.rate": {"min": 0.0, "max": 0.06},
        "rates.malaysian_60_plus.employer.rate": {"min": 0.04, "max": 0.08},
        "rates.non_malaysian_after_aug98.employee.rate": {"min": 0.0, "max": 0.12},
        "rates.non_malaysian_after_aug98.employer.rate": {"min": 0.0, "max": 0.15},
    },
    "minimum_wage": {
        "rates.nationwide.monthly": {"min": 1200, "max": 3000},
        "rates.nationwide.hourly": {"min": 5.0, "max": 20.0},
    },
    "socso_rates": {
        "wage_ceiling": {"min": 4000, "max": 10000},
    },
    "eis_rates": {
        "wage_ceiling": {"min": 4000, "max": 10000},
    },
    "hrdf_rates": {
        "rates.mandatory.rate": {"min": 0.005, "max": 0.02},
        "rates.optional.rate": {"min": 0.001, "max": 0.01},
    },
    "pcb_table": {
        "tax_rebates.threshold": {"min": 20000, "max": 50000},
        "tax_rebates.category_1_3": {"min": 0, "max": 1000},
        "tax_rebates.category_2": {"min": 0, "max": 2000},
    },
}

# Magnitude check: flag if rate changes by more than this fraction
MAGNITUDE_THRESHOLDS: dict[str, float] = {
    "epf_rates": 0.3,       # 30% change is suspicious
    "socso_rates": 0.3,
    "eis_rates": 0.3,
    "minimum_wage": 0.5,    # 50% — minimum wage jumps are bigger
    "hrdf_rates": 0.5,
    "pcb_table": 0.5,
    "public_holidays": 1.0, # holidays can change completely year-to-year
    "foreign_worker_rates": 0.3,
}

# Required top-level keys per scraper
REQUIRED_KEYS: dict[str, list[str]] = {
    "epf_rates": ["source", "year", "rates"],
    "socso_rates": ["source", "year", "wage_ceiling", "rate_table"],
    "eis_rates": ["source", "year", "wage_ceiling", "rate_table"],
    "pcb_table": ["source", "year", "tax_brackets"],
    "minimum_wage": ["source", "year", "rates"],
    "hrdf_rates": ["source", "year", "rates"],
    "public_holidays": ["source", "year", "national"],
    "foreign_worker_rates": ["source", "year", "epf", "socso", "eis"],
}


def _get_nested(data: dict, path: str) -> Any:
    """Get a value from nested dict using dot-separated path."""
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _is_numeric(value: Any) -> bool:
    """Check if value is a number."""
    return isinstance(value, (int, float))


class RateValidator:
    """Validates scraped rate data against known rules."""

    def __init__(
        self,
        range_rules: dict | None = None,
        magnitude_thresholds: dict | None = None,
        required_keys: dict | None = None,
    ):
        self.range_rules = range_rules or RANGE_RULES
        self.magnitude_thresholds = magnitude_thresholds or MAGNITUDE_THRESHOLDS
        self.required_keys = required_keys or REQUIRED_KEYS

    def validate(
        self,
        scraper_name: str,
        data: dict,
        old_data: dict | None = None,
    ) -> list[ValidationError]:
        """Run all validations. Returns list of issues (empty = clean)."""
        errors: list[ValidationError] = []

        # Strip _metadata for validation
        clean = {k: v for k, v in data.items() if k != "_metadata"}

        errors.extend(self._check_schema(scraper_name, clean))
        errors.extend(self._check_ranges(scraper_name, clean))
        if old_data:
            old_clean = {k: v for k, v in old_data.items() if k != "_metadata"}
            errors.extend(self._check_magnitude(scraper_name, old_clean, clean))

        return errors

    def _check_schema(self, scraper_name: str, data: dict) -> list[ValidationError]:
        """Check required fields exist."""
        errors = []
        required = self.required_keys.get(scraper_name, [])
        for key in required:
            if key not in data:
                errors.append(ValidationError(
                    scraper=scraper_name,
                    path=key,
                    rule="schema",
                    message=f"Required field '{key}' is missing",
                    severity="error",
                ))
        return errors

    def _check_ranges(self, scraper_name: str, data: dict) -> list[ValidationError]:
        """Check numeric values are within expected ranges."""
        errors = []
        rules = self.range_rules.get(scraper_name, {})
        for path, bounds in rules.items():
            value = _get_nested(data, path)
            if value is None:
                continue  # Missing field caught by schema check
            if not _is_numeric(value):
                continue
            if value < bounds["min"] or value > bounds["max"]:
                errors.append(ValidationError(
                    scraper=scraper_name,
                    path=path,
                    rule="range",
                    message=f"Value {value} outside expected range [{bounds['min']}, {bounds['max']}]",
                    severity="warning",
                ))
        return errors

    def _check_magnitude(
        self, scraper_name: str, old_data: dict, new_data: dict
    ) -> list[ValidationError]:
        """Flag numeric values that changed by more than the threshold."""
        errors = []
        threshold = self.magnitude_thresholds.get(scraper_name, 0.5)
        rules = self.range_rules.get(scraper_name, {})

        # Check configured paths
        for path in rules:
            old_val = _get_nested(old_data, path)
            new_val = _get_nested(new_data, path)
            if old_val is None or new_val is None:
                continue
            if not (_is_numeric(old_val) and _is_numeric(new_val)):
                continue
            if old_val == 0:
                continue
            change = abs(new_val - old_val) / abs(old_val)
            if change > threshold:
                errors.append(ValidationError(
                    scraper=scraper_name,
                    path=path,
                    rule="magnitude",
                    message=f"Value changed {change:.0%} ({old_val} -> {new_val}), "
                            f"exceeds {threshold:.0%} threshold",
                    severity="warning",
                ))

        # Also scan all leaf numeric values not in rules
        self._scan_magnitude_recursive(
            scraper_name, old_data, new_data, "", threshold, errors, set(rules.keys())
        )

        return errors

    def _scan_magnitude_recursive(
        self,
        scraper_name: str,
        old: dict,
        new: dict,
        path: str,
        threshold: float,
        errors: list[ValidationError],
        skip_paths: set[str],
    ) -> None:
        """Recursively scan for large numeric changes."""
        for key in set(old.keys()) | set(new.keys()):
            current_path = f"{path}.{key}" if path else key
            if current_path in skip_paths:
                continue
            if key not in old or key not in new:
                continue
            old_val = old[key]
            new_val = new[key]
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                self._scan_magnitude_recursive(
                    scraper_name, old_val, new_val, current_path,
                    threshold, errors, skip_paths,
                )
            elif _is_numeric(old_val) and _is_numeric(new_val) and old_val != 0:
                o, n = float(old_val), float(new_val)  # type: ignore[arg-type]
                change = abs(n - o) / abs(o)
                if change > threshold:
                    errors.append(ValidationError(
                        scraper=scraper_name,
                        path=current_path,
                        rule="magnitude",
                        message=f"Value changed {change:.0%} ({old_val} -> {new_val})",
                        severity="warning",
                    ))


def validate_and_report(
    scraper_name: str,
    data: dict,
    old_data: dict | None = None,
    strict: bool = False,
) -> tuple[list[ValidationError], bool]:
    """Validate data and report results.

    Args:
        scraper_name: Name of the scraper.
        data: New scraped data.
        old_data: Previous data (for magnitude checks).
        strict: If True, any warning blocks the save.

    Returns:
        (errors, should_proceed) — should_proceed is False if strict mode blocked.
    """
    validator = RateValidator()
    errors = validator.validate(scraper_name, data, old_data)

    if not errors:
        return [], True

    for err in errors:
        prefix = "BLOCKED" if strict and err.severity == "warning" else err.severity.upper()
        print(f"    [{prefix}] {err.path}: {err.message} ({err.rule})")

    if strict:
        any_errors = any(e.severity == "error" for e in errors)
        any_warnings = any(e.severity == "warning" for e in errors)
        if any_errors or any_warnings:
            print(f"    STRICT MODE: {len(errors)} issue(s) found, not saving.")
            return errors, False
    else:
        # Even without strict, block on schema errors (missing required fields)
        if any(e.severity == "error" for e in errors):
            print(f"    BLOCKED: {sum(1 for e in errors if e.severity == 'error')} schema error(s).")
            return errors, False

    return errors, True
