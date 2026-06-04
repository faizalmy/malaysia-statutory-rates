"""Data freshness status for statutory rate files.

Shows when each rate file was last scraped and whether it's fresh,
stale, or outdated.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Freshness thresholds (days)
FRESH_DAYS = 7
STALE_DAYS = 30


def rates_status(
    data_dir: Path | None = None,
    fresh_days: int = FRESH_DAYS,
    stale_days: int = STALE_DAYS,
) -> list[dict[str, Any]]:
    """Get freshness status for all rate data files.

    Args:
        data_dir: Path to data/ directory. Defaults to package data.
        fresh_days: Threshold for "fresh" status (default 7).
        stale_days: Threshold for "stale" status (default 30).

    Returns:
        List of dicts with keys: name, source, last_scraped, age_days, freshness.
        freshness is one of: "fresh", "stale", "old", "missing".
    """
    if data_dir is None:
        data_dir = Path(__file__).parent / "data"

    now = datetime.now(timezone.utc)
    results = []

    for json_file in sorted(data_dir.glob("*.json")):
        if json_file.name.startswith("_"):
            continue

        name = json_file.stem
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            results.append({
                "name": name,
                "source": None,
                "last_scraped": None,
                "age_days": None,
                "freshness": "error",
            })
            continue

        metadata = data.get("_metadata", {})
        scraped_at = metadata.get("scraped_at")
        source = metadata.get("source") or data.get("source", "")

        if not scraped_at:
            results.append({
                "name": name,
                "source": source,
                "last_scraped": None,
                "age_days": None,
                "freshness": "missing",
            })
            continue

        try:
            scraped_dt = datetime.fromisoformat(scraped_at)
            if scraped_dt.tzinfo is None:
                scraped_dt = scraped_dt.replace(tzinfo=timezone.utc)
            age_days = (now - scraped_dt).days
        except (ValueError, TypeError):
            results.append({
                "name": name,
                "source": source,
                "last_scraped": scraped_at,
                "age_days": None,
                "freshness": "error",
            })
            continue

        if age_days <= fresh_days:
            freshness = "fresh"
        elif age_days <= stale_days:
            freshness = "stale"
        else:
            freshness = "old"

        results.append({
            "name": name,
            "source": source,
            "last_scraped": scraped_at[:10] if scraped_at else None,
            "age_days": age_days,
            "freshness": freshness,
        })

    return results


FRESHNESS_ICONS = {
    "fresh": "\u2705",
    "stale": "\u26a0\ufe0f ",
    "old": "\u274c",
    "missing": "\u274c",
    "error": "\u274c",
}


def format_status_table(
    statuses: list[dict[str, Any]],
) -> str:
    """Format status list as an ASCII table.

    Args:
        statuses: Output from rates_status().

    Returns:
        Formatted string.
    """
    if not statuses:
        return "No data files found."

    # Header
    lines = []
    lines.append(f"{'Rate':<24} {'Last Scraped':<14} {'Age':>6}  {'Status':<6}  Source")
    lines.append("\u2500" * 80)

    for s in statuses:
        name = s["name"]
        last = s.get("last_scraped") or "never"
        age = f"{s['age_days']}d" if s.get("age_days") is not None else "—"
        freshness = s["freshness"]
        icon = FRESHNESS_ICONS.get(freshness, "?")
        source = s.get("source", "") or ""
        # Truncate source for display
        if len(source) > 40:
            source = source[:37] + "..."

        lines.append(f"{name:<24} {last:<14} {age:>6}  {icon} {freshness:<5}  {source}")

    return "\n".join(lines)
