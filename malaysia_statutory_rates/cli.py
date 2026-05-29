"""CLI entry point for malaysia-rates."""

import argparse
import json
import sys

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


def cmd_show(args: argparse.Namespace) -> None:
    """Show rate data."""
    if args.rate == "all":
        data = load_rates()
    else:
        file_name = RATE_MAP.get(args.rate, args.rate)
        data = {args.rate: load_rate(file_name)}

    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_scrape(args: argparse.Namespace) -> None:
    """Run scrapers to update data files."""
    from malaysia_statutory_rates.scrapers import run_scrapers

    targets = None if args.all else args.targets
    if not targets and not args.all:
        print("Specify --all or list scrapers to run.")
        print(f"Available: {', '.join(RATE_MAP.keys())}")
        sys.exit(1)

    results = run_scrapers(targets)
    for name, changed in results.items():
        status = "UPDATED" if changed else "unchanged"
        print(f"  {name}: {status}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="malaysia-rates",
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
    scrape_p.add_argument("targets", nargs="*", help="Specific scrapers to run")

    args = parser.parse_args()

    if args.command == "show":
        cmd_show(args)
    elif args.command == "scrape":
        cmd_scrape(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
