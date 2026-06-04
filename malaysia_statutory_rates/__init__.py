"""malaysia-statutory-rates — Malaysian statutory rate data."""

from malaysia_statutory_rates.changelog import read_changelog
from malaysia_statutory_rates.loader import load_rate, load_rates

DISCLAIMER = (
    "This data is scraped from official Malaysian government websites for "
    "reference purposes only. Use at your own risk. Always verify rates "
    "against official sources before making payroll or tax decisions. "
    "See https://github.com/faizalmy/malaysia-statutory-rates/blob/main/DISCLAIMER.md"
)

__all__ = ["load_rates", "load_rate", "read_changelog", "DISCLAIMER"]
__version__ = "0.2.0"
