"""CLI entry point for the AFATADS GTCS client.

Usage:
    afatads -c config.json ingest          # connect & ingest TIDET events
    afatads -c config.json read --all      # dump all stored events
    afatads -c config.json read --date 2026-04-01
    afatads -c config.json read --range 2026-03-01 2026-04-01
    afatads -c config.json read --target AB1234
    afatads -c config.json status          # store stats
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, datetime

from afatads.client import GtcsClient
from afatads.config import ClientConfig, load_config
from afatads.store import TidetReader


def _setup_logging(cfg: ClientConfig) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if cfg.logging.file:
        handlers.append(logging.FileHandler(cfg.logging.file))
    logging.basicConfig(
        level=getattr(logging, cfg.logging.level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
        handlers=handlers,
    )


# ─── ingest ───────────────────────────────────────────────────────────────

def cmd_ingest(cfg: ClientConfig) -> None:
    client = GtcsClient(cfg)
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        pass


# ─── read ─────────────────────────────────────────────────────────────────

def cmd_read(cfg: ClientConfig, args: argparse.Namespace) -> None:
    reader = TidetReader(cfg.store)

    events = []
    if args.target:
        events = reader.find_by_target(args.target)
    elif args.date:
        d = date.fromisoformat(args.date)
        events = list(reader.iter_date(d))
    elif args.range:
        start = date.fromisoformat(args.range[0])
        end = date.fromisoformat(args.range[1])
        events = list(reader.iter_range(start, end))
    elif args.file:
        events = [reader.read_file(args.file)]
    else:
        events = list(reader.iter_all())

    for evt in events:
        print(evt.to_json())
        print()  # blank line separator


# ─── status ───────────────────────────────────────────────────────────────

def cmd_status(cfg: ClientConfig) -> None:
    reader = TidetReader(cfg.store)
    dates = reader.dates_available()
    count = reader.count()
    info = {
        "store_root": str(reader.root.resolve()),
        "total_events": count,
        "date_range": {
            "earliest": dates[0].isoformat() if dates else None,
            "latest": dates[-1].isoformat() if dates else None,
        },
        "dates_with_data": len(dates),
    }
    print(json.dumps(info, indent=2))


# ─── argparse ─────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="afatads",
        description="AFATADS GTCS client — TIDET ingestion and retrieval",
    )
    p.add_argument("-c", "--config", required=True,
                   help="Path to JSON configuration file")

    sub = p.add_subparsers(dest="command", required=True)

    # ingest
    sub.add_parser("ingest", help="Connect to GTCS endpoints and ingest TIDET events")

    # read
    rp = sub.add_parser("read", help="Read stored TIDET events")
    rg = rp.add_mutually_exclusive_group()
    rg.add_argument("--all", action="store_true", help="Dump all events")
    rg.add_argument("--date", help="Events for a single date (YYYY-MM-DD)")
    rg.add_argument("--range", nargs=2, metavar=("START", "END"),
                    help="Events in date range (YYYY-MM-DD YYYY-MM-DD)")
    rg.add_argument("--target", help="Events matching a target number")
    rg.add_argument("--file", help="Read a single TIDET file by path")

    # status
    sub.add_parser("status", help="Show store statistics")

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    _setup_logging(cfg)

    if args.command == "ingest":
        cmd_ingest(cfg)
    elif args.command == "read":
        cmd_read(cfg, args)
    elif args.command == "status":
        cmd_status(cfg)


if __name__ == "__main__":
    main()
