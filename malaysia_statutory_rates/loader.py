"""Load statutory rate data from bundled JSON files."""

import json
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).parent / "data"


def load_rates() -> dict[str, Any]:
    """Load all statutory rate files and return as a single dict.

    Returns:
        Dict keyed by file stem, e.g. {"epf_rates": {...}, "minimum_wage": {...}, ...}
    """
    rates = {}
    for json_file in sorted(_DATA_DIR.glob("*.json")):
        rates[json_file.stem] = json.loads(json_file.read_text(encoding="utf-8"))
    return rates


def load_rate(name: str) -> dict[str, Any]:
    """Load a single rate file by name.

    Args:
        name: File stem, e.g. "epf_rates", "minimum_wage", "public_holidays"

    Returns:
        Parsed JSON content.

    Raises:
        FileNotFoundError: If the rate file doesn't exist.
    """
    path = _DATA_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Rate file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
