"""
Shared utilities for CFl_data backfill runs.

Backfill semantics (mirrors the daily batch pipeline):
  - TARGET_DATE  : partition date written to R2  (year=/month=/day=)
  - SCRAPE_DATE  : TARGET_DATE - 1 day — listings filtered by this publish date

Scrapers normally call datetime.now() for save_date and datetime.now()-1day for
scrape_date.  We patch datetime.datetime.now() to return TARGET_DATE at noon so
existing category code works unchanged.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Callable, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

CFL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# slug -> config.  account = DataImpulse account (1=Batch A, 2=Batch B, 3=Batch C)
CATEGORIES: Dict[str, dict] = {
    "animals": {
        "dir": "Animals",
        "script": "main.py",
        "account": 1,
    },
    "bikes": {
        "dir": "bikes",
        "script": "main.py",
        "account": 1,
    },
    "gifts": {
        "dir": "gifts",
        "script": "main.py",
        "account": 1,
    },
    "camping": {
        "dir": "Camping",
        "script": "main.py",
        "account": 1,
    },
    "property": {
        "dir": "Property",
        "script": "main.py",
        "account": 1,
    },
    "new-car": {
        "dir": "New Car",
        "script": "main.py",
        "account": 1,
        "runner": "new_car",
    },
    "rest-automotive-part1": {
        "dir": "Rest-Automotive-Part1",
        "script": "main.py",
        "account": 1,
    },
    "jobs": {
        "dir": "Jobs",
        "script": "main.py",
        "account": 1,
    },
    "sport": {
        "dir": "Sport",
        "script": "main.py",
        "account": 1,
    },
    "used-car": {
        "dir": "Used Car",
        "script": "main_used_cars.py",
        "account": 2,
    },
    "others": {
        "dir": "Others",
        "script": "main.py",
        "account": 2,
    },
    "education": {
        "dir": "Education",
        "script": "main.py",
        "account": 2,
    },
    "fashion-and-family": {
        "dir": "Fashion-and-Family",
        "script": "main.py",
        "account": 2,
    },
    "services": {
        "dir": "Services",
        "script": "main.py",
        "account": 2,
    },
    "contracting": {
        "dir": "Contracting",
        "script": "main.py",
        "account": 2,
    },
    "rest-automotive-part2": {
        "dir": "Rest-Automotive-Part2",
        "script": "main.py",
        "account": 2,
    },
    "dalil": {
        "dir": "Dalil",
        "script": "main.py",
        "account": 3,
    },
    "automotive-cars-and-trucks": {
        "dir": "Automotive-Cars-and-Trucks",
        "script": "main.py",
        "account": 3,
    },
    "electronics": {
        "dir": "Electronics",
        "script": "main.py",
        "account": 3,
    },
    "wanted-cars": {
        "dir": "Wanted-Cars",
        "script": "main.py",
        "account": 3,
    },
    "furniture": {
        "dir": "Furniture",
        "script": "main.py",
        "account": 3,
    },
    "commercials": {
        "dir": "Commercials",
        "script": "main.py",
        "account": 3,
    },
    "rest-automotive-part3": {
        "dir": "Rest-Automotive-Part3",
        "script": "main.py",
        "account": 3,
    },
}


def category_choices() -> List[str]:
    return sorted(CATEGORIES.keys())


def parse_date(value: str, label: str) -> datetime:
    value = (value or "").strip()
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise SystemExit(
            f"ERROR: Invalid {label} '{value}'. Expected format: YYYY-MM-DD"
        ) from exc


def iter_target_dates(start: datetime, end: datetime) -> Iterator[datetime]:
    if end < start:
        raise SystemExit(
            f"ERROR: end_date ({end.strftime('%Y-%m-%d')}) "
            f"must be on or after start_date ({start.strftime('%Y-%m-%d')})"
        )
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def geo_for_account(account: int, target_date: datetime) -> str:
    """Return __cr.XX geo suffix for a DataImpulse account and target date."""
    dow = int(target_date.strftime("%w"))  # 0=Sun … 6=Sat
    rotations = {
        1: {0: "eg", 1: "kw", 2: "sa", 3: "kw", 4: "sa", 5: "kw", 6: "sa"},
        2: {0: "kw", 1: "sa", 2: "eg", 3: "sa", 4: "eg", 5: "sa", 6: "eg"},
        3: {0: "sa", 1: "eg", 2: "kw", 3: "eg", 4: "kw", 5: "eg", 6: "kw"},
    }
    try:
        return rotations[account][dow]
    except KeyError as exc:
        raise SystemExit(f"ERROR: Unknown account {account}") from exc


def resolve_category(name: str) -> dict:
    key = (name or "").strip().lower()
    if key not in CATEGORIES:
        valid = ", ".join(category_choices())
        raise SystemExit(
            f"ERROR: Unknown category '{name}'. Valid options: {valid}"
        )
    return CATEGORIES[key]


def _preimport_datetime_subclassers() -> None:
    """
    Import libraries that subclass datetime.datetime at load time.

    patched_datetime replaces datetime.datetime with a dynamic subclass, which
    breaks those imports (e.g. pandas ABCTimestamp). Pre-import while the real
    class is still in place; later category imports reuse sys.modules cache.
    """
    if "pandas" not in sys.modules:
        import pandas  # noqa: F401


@contextmanager
def patched_datetime(target_date: datetime) -> Iterator[None]:
    """
    Patch datetime.datetime.now() to return target_date at noon UTC-local naive.
    Must be active before importing any category module (Property sets module-level
    constants at import time).
    """
    _preimport_datetime_subclassers()
    import datetime as dt_module

    frozen = target_date.replace(hour=12, minute=0, second=0, microsecond=0)
    original = dt_module.datetime

    class _BackfillDateTime(original):
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return frozen.astimezone(tz)
            return frozen

        @classmethod
        def utcnow(cls):
            return frozen

    dt_module.datetime = _BackfillDateTime
    try:
        yield
    finally:
        dt_module.datetime = original


def _load_module(category_dir: str, script: str):
    script_path = os.path.join(category_dir, script)
    if not os.path.isfile(script_path):
        raise SystemExit(f"ERROR: Scraper script not found: {script_path}")

    module_name = f"backfill_{os.path.basename(category_dir).replace(' ', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"ERROR: Could not load module from {script_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


async def _run_new_car(category_dir: str) -> int:
    module = _load_module(category_dir, "main.py")
    bucket = os.environ.get("CF_R2_BUCKET_NAME")
    if not bucket:
        raise SystemExit("ERROR: CF_R2_BUCKET_NAME environment variable is required")

    url = "https://www.q84sale.com/ar/automotive/new-cars-1"
    scraper = module.MainScraper(url, bucket)
    await scraper.scrape_and_save()
    return 0


async def _run_module_main(module) -> int:
    if not hasattr(module, "main"):
        raise SystemExit("ERROR: Category script has no main() entry point")

    result = module.main()
    if asyncio.iscoroutine(result):
        result = await result
    if result is None:
        return 0
    return int(result)


def run_single(category_key: str, target_date: datetime) -> int:
    """Run one category for one TARGET_DATE partition."""
    config = resolve_category(category_key)
    category_dir = os.path.join(CFL_ROOT, config["dir"])
    scrape_date = target_date - timedelta(days=1)

    os.environ["TARGET_DATE"] = target_date.strftime("%Y-%m-%d")
    os.environ["BACKFILL_TARGET_DATE"] = target_date.strftime("%Y-%m-%d")
    os.environ["BACKFILL_SCRAPE_DATE"] = scrape_date.strftime("%Y-%m-%d")

    logger.info(
        "[BACKFILL] category=%s  save=%s  scrape=%s",
        category_key,
        target_date.strftime("%Y-%m-%d"),
        scrape_date.strftime("%Y-%m-%d"),
    )

    previous_cwd = os.getcwd()
    try:
        os.chdir(category_dir)
        if CFL_ROOT not in sys.path:
            sys.path.insert(0, CFL_ROOT)
        if category_dir not in sys.path:
            sys.path.insert(0, category_dir)

        with patched_datetime(target_date):
            if config.get("runner") == "new_car":
                return asyncio.run(_run_new_car(category_dir))

            module = _load_module(category_dir, config["script"])
            return asyncio.run(_run_module_main(module))
    finally:
        os.chdir(previous_cwd)
