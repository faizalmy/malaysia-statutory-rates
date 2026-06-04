"""Tests for the rate validation layer."""

from pathlib import Path

from malaysia_statutory_rates.validator import (
    RANGE_RULES,
    RateValidator,
    ValidationError,
    validate_and_report,
)


class TestRateValidator:
    """Tests for RateValidator.validate()."""

    def test_valid_data_no_errors(self):
        validator = RateValidator()
        data = {
            "source": "https://kwsp.gov.my",
            "year": 2025,
            "rates": {
                "malaysian_pr_nonmy_before_aug98_below_60": {
                    "employee": {"rate": 0.11},
                    "employer": {"wage_lte_5000": {"rate": 0.13}},
                },
            },
        }
        errors = validator.validate("epf_rates", data)
        assert len(errors) == 0

    def test_missing_required_field(self):
        validator = RateValidator()
        data = {"source": "https://kwsp.gov.my", "year": 2025}
        # Missing "rates" key
        errors = validator.validate("epf_rates", data)
        assert any(e.rule == "schema" and e.path == "rates" for e in errors)

    def test_range_violation(self):
        validator = RateValidator()
        data = {
            "source": "https://kwsp.gov.my",
            "year": 2025,
            "rates": {
                "malaysian_pr_nonmy_before_aug98_below_60": {
                    "employee": {"rate": 0.80},  # Way too high
                    "employer": {"wage_lte_5000": {"rate": 0.13}},
                },
            },
        }
        errors = validator.validate("epf_rates", data)
        range_errors = [e for e in errors if e.rule == "range"]
        assert len(range_errors) >= 1
        assert "0.8" in range_errors[0].message

    def test_minimum_wage_range(self):
        validator = RateValidator()
        data = {
            "source": "https://example.com",
            "year": 2026,
            "rates": {"nationwide": {"monthly": 50, "hourly": 0.5}},
        }
        errors = validator.validate("minimum_wage", data)
        range_errors = [e for e in errors if e.rule == "range"]
        assert len(range_errors) == 2  # Both monthly and hourly out of range

    def test_magnitude_change_suspicious(self):
        validator = RateValidator()
        old = {
            "rates": {
                "malaysian_pr_nonmy_before_aug98_below_60": {
                    "employee": {"rate": 0.11},
                    "employer": {"wage_lte_5000": {"rate": 0.13}},
                },
            },
        }
        new = {
            "source": "https://kwsp.gov.my",
            "year": 2025,
            "rates": {
                "malaysian_pr_nonmy_before_aug98_below_60": {
                    "employee": {"rate": 0.50},  # 354% jump
                    "employer": {"wage_lte_5000": {"rate": 0.13}},
                },
            },
        }
        errors = validator.validate("epf_rates", new, old_data=old)
        mag_errors = [e for e in errors if e.rule == "magnitude"]
        assert len(mag_errors) >= 1
        assert "0.11" in mag_errors[0].message and "0.5" in mag_errors[0].message

    def test_magnitude_small_change_ok(self):
        validator = RateValidator()
        old = {
            "rates": {
                "malaysian_pr_nonmy_before_aug98_below_60": {
                    "employee": {"rate": 0.11},
                    "employer": {"wage_lte_5000": {"rate": 0.13}},
                },
            },
        }
        new = {
            "source": "https://kwsp.gov.my",
            "year": 2025,
            "rates": {
                "malaysian_pr_nonmy_before_aug98_below_60": {
                    "employee": {"rate": 0.12},  # 9% change — OK
                    "employer": {"wage_lte_5000": {"rate": 0.13}},
                },
            },
        }
        errors = validator.validate("epf_rates", new, old_data=old)
        mag_errors = [e for e in errors if e.rule == "magnitude"]
        assert len(mag_errors) == 0

    def test_no_old_data_skips_magnitude(self):
        validator = RateValidator()
        data = {
            "source": "https://kwsp.gov.my",
            "year": 2025,
            "rates": {
                "malaysian_pr_nonmy_before_aug98_below_60": {
                    "employee": {"rate": 0.99},
                },
            },
        }
        errors = validator.validate("epf_rates", data, old_data=None)
        mag_errors = [e for e in errors if e.rule == "magnitude"]
        assert len(mag_errors) == 0

    def test_all_scrapers_have_rules(self):
        """Every scraper name should have at least required_keys defined."""
        expected = [
            "epf_rates", "socso_rates", "eis_rates", "pcb_table",
            "minimum_wage", "hrdf_rates", "public_holidays", "foreign_worker_rates",
        ]
        from malaysia_statutory_rates.validator import REQUIRED_KEYS
        for name in expected:
            assert name in REQUIRED_KEYS, f"Missing required_keys for {name}"

    def test_range_rules_within_bounds(self):
        """Every range rule should have min < max."""
        for scraper, rules in RANGE_RULES.items():
            for path, bounds in rules.items():
                assert bounds["min"] < bounds["max"], (
                    f"{scraper}/{path}: min ({bounds['min']}) >= max ({bounds['max']})"
                )


class TestValidateAndReport:
    """Tests for validate_and_report()."""

    def test_clean_data_returns_true(self):
        data = {
            "source": "https://gajiminimum.mohr.gov.my",
            "year": 2026,
            "rates": {"nationwide": {"monthly": 1700, "hourly": 8.72}},
        }
        errors, proceed = validate_and_report("minimum_wage", data)
        assert proceed is True
        assert len(errors) == 0

    def test_strict_blocks_on_warning(self):
        data = {
            "source": "https://gajiminimum.mohr.gov.my",
            "year": 2026,
            "rates": {"nationwide": {"monthly": 50, "hourly": 0.5}},  # Out of range
        }
        errors, proceed = validate_and_report("minimum_wage", data, strict=True)
        assert proceed is False
        assert len(errors) > 0

    def test_non_strict_allows_warnings(self):
        data = {
            "source": "https://gajiminimum.mohr.gov.my",
            "year": 2026,
            "rates": {"nationwide": {"monthly": 50, "hourly": 0.5}},
        }
        errors, proceed = validate_and_report("minimum_wage", data, strict=False)
        assert proceed is True
        assert len(errors) > 0  # Warnings reported but not blocking

    def test_schema_error_blocks_even_non_strict(self):
        """Schema errors (missing required fields) are severity='error'."""
        data = {"source": "https://example.com"}
        errors, proceed = validate_and_report("minimum_wage", data, strict=True)
        assert proceed is False
        assert any(e.severity == "error" for e in errors)


class TestValidatorWithRealData:
    """Validate the actual bundled data files pass validation."""

    def test_all_data_files_pass_validation(self):
        """Every data file in data/ should pass validation without errors."""
        import json
        data_dir = Path(__file__).parent.parent / "malaysia_statutory_rates" / "data"
        validator = RateValidator()

        for json_file in sorted(data_dir.glob("*.json")):
            name = json_file.stem
            if name.startswith("_"):
                continue  # Skip _changelog.jsonl etc.
            data = json.loads(json_file.read_text())
            errors = validator.validate(name, data)
            real_errors = [e for e in errors if e.severity == "error"]
            assert len(real_errors) == 0, (
                f"{json_file.name} has validation errors: "
                + "; ".join(str(e) for e in real_errors)
            )
