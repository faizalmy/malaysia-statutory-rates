"""Tests for the loader module."""

import pytest

from malaysia_statutory_rates.loader import load_rate, load_rates


def test_load_rates_returns_dict():
    rates = load_rates()
    assert isinstance(rates, dict)
    assert len(rates) > 0


def test_load_rates_contains_minimum_wage():
    rates = load_rates()
    assert "minimum_wage" in rates


def test_load_rate_minimum_wage():
    data = load_rate("minimum_wage")
    assert data["rates"]["nationwide"]["monthly"] == 1700


def test_load_rate_not_found():
    with pytest.raises(FileNotFoundError):
        load_rate("nonexistent_rate")
