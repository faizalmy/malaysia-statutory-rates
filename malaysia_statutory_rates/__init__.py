"""malaysia-statutory-rates — Malaysian statutory rate data."""

from malaysia_statutory_rates.changelog import read_changelog
from malaysia_statutory_rates.loader import load_rate, load_rates

__all__ = ["load_rates", "load_rate", "read_changelog"]
__version__ = "0.1.1"
