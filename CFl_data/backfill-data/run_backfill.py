#!/usr/bin/env python3
"""
Backfill runner for CFl_data categories.

Single date:
  CATEGORY=camping TARGET_DATE=2026-08-02 python run_backfill.py

Date range (inclusive):
  CATEGORY=camping START_DATE=2026-08-01 END_DATE=2026-08-06 python run_backfill.py

For each TARGET_DATE in the range the scraper fetches listings published on
TARGET_DATE - 1 day and writes to year=YYYY/month=MM/day=DD/ using TARGET_DATE.
"""

from __future__ import annotations

import logging
import os
import sys

BACKFILL_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKFILL_DIR not in sys.path:
    sys.path.insert(0, BACKFILL_DIR)

from backfill_utils import (  # noqa: E402
    iter_target_dates,
    parse_date,
    resolve_category,
    run_single,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _resolve_dates() -> list:
    target = os.environ.get("TARGET_DATE", "").strip()
    start = os.environ.get("START_DATE", "").strip()
    end = os.environ.get("END_DATE", "").strip()

    if target:
        dt = parse_date(target, "TARGET_DATE")
        return [dt]

    if not start:
        raise SystemExit(
            "ERROR: Set TARGET_DATE for a single day, or START_DATE (+ optional END_DATE) for a range."
        )

    start_dt = parse_date(start, "START_DATE")
    end_dt = parse_date(end or start, "END_DATE")
    return list(iter_target_dates(start_dt, end_dt))


def main() -> int:
    category = os.environ.get("CATEGORY", "").strip()
    if not category:
        raise SystemExit("ERROR: CATEGORY environment variable is required.")

    resolve_category(category)
    dates = _resolve_dates()

    logger.info(
        "Starting backfill — category=%s  dates=%s → %s  (%d day(s))",
        category,
        dates[0].strftime("%Y-%m-%d"),
        dates[-1].strftime("%Y-%m-%d"),
        len(dates),
    )

    failures = 0
    for target_dt in dates:
        label = target_dt.strftime("%Y-%m-%d")
        logger.info("=" * 60)
        logger.info("Processing TARGET_DATE=%s", label)
        logger.info("=" * 60)
        try:
            exit_code = run_single(category, target_dt)
            if exit_code != 0:
                failures += 1
                logger.error("Backfill failed for %s (exit %s)", label, exit_code)
        except SystemExit as exc:
            failures += 1
            logger.error("Backfill failed for %s: %s", label, exc)
        except Exception as exc:
            failures += 1
            logger.exception("Backfill failed for %s: %s", label, exc)

    logger.info("=" * 60)
    if failures:
        logger.error(
            "Backfill finished with %d failure(s) out of %d date(s).",
            failures,
            len(dates),
        )
        return 1

    logger.info("Backfill completed successfully for %d date(s).", len(dates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
