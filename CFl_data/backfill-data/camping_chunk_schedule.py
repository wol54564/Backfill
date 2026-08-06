#!/usr/bin/env python3
"""
Camping backfill split across 3 calendar run-days.

Full target range: 2026-07-21 → 2026-08-06

Run calendar (local plan; GitHub Actions uses UTC date of the job):
  Day 1 — 2026-08-07  →  TARGET 2026-07-21 … 2026-07-26
  Day 2 — 2026-08-08  →  TARGET 2026-07-27 … 2026-07-31
  Day 3 — 2026-08-09  →  TARGET 2026-08-01 … 2026-08-06

Usage:
  # Resolve chunk for "today" (UTC) and print start/end for GITHUB_OUTPUT
  python camping_chunk_schedule.py

  # Force a chunk (manual re-run): day 1|2|3
  python camping_chunk_schedule.py --day 2

  # Override which calendar date is treated as "today"
  python camping_chunk_schedule.py --run-date 2026-08-08
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from typing import Dict, Optional, Tuple

CATEGORY = "camping"

# run_date (when the workflow fires) → (start_date, end_date) inclusive TARGET_DATEs
CHUNKS: Dict[date, Tuple[date, date]] = {
    date(2026, 8, 7): (date(2026, 7, 21), date(2026, 7, 26)),
    date(2026, 8, 8): (date(2026, 7, 27), date(2026, 7, 31)),
    date(2026, 8, 9): (date(2026, 8, 1), date(2026, 8, 6)),
}

# Explicit day index → same ranges (for workflow_dispatch --day N)
DAY_CHUNKS: Dict[int, Tuple[date, date]] = {
    1: (date(2026, 7, 21), date(2026, 7, 26)),
    2: (date(2026, 7, 27), date(2026, 7, 31)),
    3: (date(2026, 8, 1), date(2026, 8, 6)),
}


def _parse_iso(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def resolve_chunk(
    run_date: Optional[date] = None,
    day: Optional[int] = None,
) -> Tuple[date, date, int]:
    """
    Return (start, end, day_number).

    Prefer explicit --day; otherwise map run_date to CHUNKS.
    """
    if day is not None:
        if day not in DAY_CHUNKS:
            raise SystemExit(f"ERROR: --day must be 1, 2, or 3 (got {day})")
        start, end = DAY_CHUNKS[day]
        return start, end, day

    if run_date is None:
        run_date = date.today()

    if run_date not in CHUNKS:
        known = ", ".join(d.isoformat() for d in sorted(CHUNKS))
        raise SystemExit(
            f"ERROR: No camping chunk scheduled for run date {run_date.isoformat()}. "
            f"Known run dates: {known}. Use --day 1|2|3 to force a chunk."
        )

    start, end = CHUNKS[run_date]
    day_num = sorted(CHUNKS.keys()).index(run_date) + 1
    return start, end, day_num


def emit_github_output(start: date, end: date, day: int) -> None:
    lines = [
        f"category={CATEGORY}",
        f"start_date={start.isoformat()}",
        f"end_date={end.isoformat()}",
        f"day={day}",
        f"skip=false",
    ]
    out_path = os.environ.get("GITHUB_OUTPUT")
    if out_path:
        with open(out_path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    for line in lines:
        print(line)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve camping 3-day backfill chunk")
    parser.add_argument(
        "--day",
        type=int,
        choices=[1, 2, 3],
        help="Force chunk day 1, 2, or 3 (manual re-run)",
    )
    parser.add_argument(
        "--run-date",
        type=str,
        help="Calendar date of the run (YYYY-MM-DD). Defaults to today (UTC on Actions).",
    )
    parser.add_argument(
        "--allow-skip",
        action="store_true",
        help="If run date has no chunk, emit skip=true instead of exiting.",
    )
    args = parser.parse_args(argv)

    run_date = _parse_iso(args.run_date) if args.run_date else date.today()

    try:
        start, end, day = resolve_chunk(run_date=run_date, day=args.day)
    except SystemExit as exc:
        if args.allow_skip and args.day is None:
            msg = str(exc)
            print(msg, file=sys.stderr)
            out_path = os.environ.get("GITHUB_OUTPUT")
            lines = ["skip=true", "category=camping", "start_date=", "end_date=", "day="]
            if out_path:
                with open(out_path, "a", encoding="utf-8") as fh:
                    fh.write("\n".join(lines) + "\n")
            for line in lines:
                print(line)
            return 0
        raise

    days = (end - start).days + 1
    print("=============================================")
    print(f"CAMPING CHUNK Day {day}/3")
    print(f"Run date   : {run_date.isoformat()}")
    print(f"TARGET     : {start.isoformat()} -> {end.isoformat()}  ({days} day(s))")
    print("=============================================")
    emit_github_output(start, end, day)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
