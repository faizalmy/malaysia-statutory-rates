"""CLI entry point for malaysia-statutory-rates."""

import argparse
import json
import sys
from pathlib import Path

from malaysia_statutory_rates.loader import load_rate, load_rates

# Friendly name -> filename mapping
RATE_MAP = {
    "epf": "epf_rates",
    "socso": "socso_rates",
    "eis": "eis_rates",
    "pcb": "pcb_table",
    "minimum-wage": "minimum_wage",
    "hrdf": "hrdf_rates",
    "holidays": "public_holidays",
    "foreign-workers": "foreign_worker_rates",
}


def _print_disclaimer() -> None:
    """Print disclaimer notice."""
    from malaysia_statutory_rates import DISCLAIMER
    print(f"\n⚠️  {DISCLAIMER}")


def cmd_show(args: argparse.Namespace) -> None:
    """Show rate data."""
    if args.rate == "all":
        data = load_rates()
    else:
        file_name = RATE_MAP.get(args.rate, args.rate)
        data = {args.rate: load_rate(file_name)}

    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_changelog(args: argparse.Namespace) -> None:
    """Show changelog entries."""
    from malaysia_statutory_rates.changelog import read_changelog

    data_dir = Path(__file__).parent / "data"
    entries = read_changelog(data_dir, last_n=args.last)

    if not entries:
        print("No changelog entries found.")
        return

    for entry in entries:
        ts = entry["ts"][:19].replace("T", " ")
        scraper = entry["scraper"]
        count = entry.get("change_count", len(entry.get("changes", [])))
        print(f"\n[{ts}] {scraper} — {count} change(s)")
        for change in entry.get("changes", []):
            ctype = change["type"]
            path = change["path"]
            if ctype == "modified":
                old = change["old"]
                new = change["new"]
                print(f"  ~ {path}: {old!r} -> {new!r}")
            elif ctype == "added":
                print(f"  + {path}: {change['new']!r}")
            elif ctype == "removed":
                print(f"  - {path}: {change['old']!r}")


def cmd_status(args: argparse.Namespace) -> None:
    """Show data freshness status."""
    from malaysia_statutory_rates.status import format_status_table, rates_status

    data_dir = Path(__file__).parent / "data"
    statuses = rates_status(data_dir)
    print(format_status_table(statuses))


def cmd_scrape(args: argparse.Namespace) -> None:
    """Run scrapers to update data files."""
    from malaysia_statutory_rates.scrapers import run_scrapers

    targets = None if args.all else args.targets
    if not targets and not args.all:
        print("Specify --all or list scrapers to run.")
        print(f"Available: {', '.join(RATE_MAP.keys())}")
        sys.exit(1)

    results = run_scrapers(targets, strict=args.strict)
    for name, changed in results.items():
        status = "UPDATED" if changed else "unchanged"
        print(f"  {name}: {status}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="malaysia-statutory-rates",
        description="Malaysian statutory rate data — view and scrape.",
    )
    sub = parser.add_subparsers(dest="command")

    # show
    show_p = sub.add_parser("show", help="Display rate data")
    show_p.add_argument(
        "rate",
        nargs="?",
        default="all",
        help="Rate name (epf, socso, eis, pcb, minimum-wage, hrdf, holidays, all)",
    )

    # scrape
    scrape_p = sub.add_parser("scrape", help="Run scrapers to update data")
    scrape_p.add_argument("--all", action="store_true", help="Scrape all sources")
    scrape_p.add_argument(
        "--strict", action="store_true",
        help="Block saving if validation warnings are found"
    )
    scrape_p.add_argument("targets", nargs="*", help="Specific scrapers to run")

    # changelog
    changelog_p = sub.add_parser("changelog", help="Show data change history")
    changelog_p.add_argument(
        "--last", type=int, default=None, help="Show only last N entries"
    )

    # status
    sub.add_parser("status", help="Show data freshness status")

    args = parser.parse_args()

    if args.command == "show":
        cmd_show(args)
    elif args.command == "scrape":
        cmd_scrape(args)
    elif args.command == "changelog":
        cmd_changelog(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        parser.print_help()
        sys.exit(1)

    _print_disclaimer()


if __name__ == "__main__":
    main()
