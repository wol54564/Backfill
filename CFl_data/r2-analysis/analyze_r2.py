"""
Analyze Cloudflare R2 storage by file type, website, and day.

Does not download objects — only lists keys and sizes.

Expected layout (Hive-style dates):
  {website}/{category?}/year=YYYY/month=MM/day=DD/...

Examples:
  4sale-data/animals/year=2026/month=08/day=01/listings.xlsx
  bleems-data/year=2026/month=08/day=01/data.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import boto3
import pandas as pd
from botocore.config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("r2-analysis")

DATE_RE = re.compile(r"year=(\d{4})/month=(\d{2})/day=(\d{2})")

EXCEL_EXTS = {".xlsx", ".xls", ".xlsm", ".xlsb"}
JSON_EXTS = {".json", ".jsonl"}
CSV_EXTS = {".csv"}
IMAGE_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
    ".svg",
    ".avif",
    ".heic",
    ".heif",
    ".ico",
    ".tif",
    ".tiff",
}

GROUP_ORDER = ["excel", "json", "csv", "image", "other"]
GROUP_LABELS = {
    "excel": "Excel",
    "json": "JSON",
    "csv": "CSV",
    "image": "Images",
    "other": "Other",
}

IMAGE_TYPE_ORDER = [
    "jpg",
    "jpeg",
    "png",
    "gif",
    "webp",
    "bmp",
    "svg",
    "avif",
    "heic",
    "heif",
    "ico",
    "tif",
    "tiff",
]


def format_size(num_bytes: int | float) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(value) < 1024.0 or unit == "PB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} PB"


def classify_extension(filename: str) -> tuple[str, str]:
    """Return (group, subtype) from a file name."""
    ext = Path(filename).suffix.lower()
    if ext in EXCEL_EXTS:
        return "excel", ext.lstrip(".")
    if ext in JSON_EXTS:
        return "json", ext.lstrip(".")
    if ext in CSV_EXTS:
        return "csv", "csv"
    if ext in IMAGE_EXTS:
        return "image", ext.lstrip(".")
    if not ext:
        return "other", "(no extension)"
    return "other", ext.lstrip(".")


def parse_object_key(key: str, root_prefix: str = "") -> dict[str, str] | None:
    """Extract website, category, date, and filename from an R2 key."""
    if key.endswith("/"):
        return None

    relative = key
    if root_prefix:
        prefix = root_prefix.rstrip("/") + "/"
        if relative.startswith(prefix):
            relative = relative[len(prefix) :]
        elif relative == root_prefix.rstrip("/"):
            return None

    if not relative or relative.endswith("/"):
        return None

    parts = [p for p in relative.split("/") if p]
    if not parts:
        return None

    website = parts[0]
    filename = parts[-1]
    match = DATE_RE.search(relative)
    day = f"{match.group(1)}-{match.group(2)}-{match.group(3)}" if match else "unknown"

    category = ""
    if match:
        before = relative[: match.start()].strip("/")
        segs = [s for s in before.split("/") if s]
        # segs[0] is website; remaining path before the date is category
        if len(segs) >= 2:
            category = "/".join(segs[1:])
    elif len(parts) > 1:
        category = "/".join(parts[1:-1])

    return {
        "website": website,
        "category": category or "(none)",
        "date": day,
        "filename": filename,
    }


class Counter:
    __slots__ = ("files", "bytes")

    def __init__(self) -> None:
        self.files = 0
        self.bytes = 0

    def add(self, size: int) -> None:
        self.files += 1
        self.bytes += size

    def as_dict(self) -> dict[str, Any]:
        return {
            "files": self.files,
            "bytes": self.bytes,
            "size": format_size(self.bytes),
        }


class BucketStats:
    def __init__(self) -> None:
        self.total = Counter()
        self.groups: dict[str, Counter] = defaultdict(Counter)
        self.image_types: dict[str, Counter] = defaultdict(Counter)
        self.other_types: dict[str, Counter] = defaultdict(Counter)
        self.excel_types: dict[str, Counter] = defaultdict(Counter)
        self.json_types: dict[str, Counter] = defaultdict(Counter)

    def add(self, group: str, subtype: str, size: int) -> None:
        self.total.add(size)
        self.groups[group].add(size)
        if group == "image":
            self.image_types[subtype].add(size)
        elif group == "excel":
            self.excel_types[subtype].add(size)
        elif group == "json":
            self.json_types[subtype].add(size)
        elif group == "other":
            self.other_types[subtype].add(size)

    def snapshot(self) -> dict[str, Any]:
        return {
            "total": self.total.as_dict(),
            "excel": self.groups["excel"].as_dict(),
            "json": self.groups["json"].as_dict(),
            "csv": self.groups["csv"].as_dict(),
            "images": {
                **self.groups["image"].as_dict(),
                "by_type": {k: v.as_dict() for k, v in sorted(self.image_types.items())},
            },
            "other": {
                **self.groups["other"].as_dict(),
                "by_type": {k: v.as_dict() for k, v in sorted(self.other_types.items())},
            },
        }


def make_r2_client(bucket_name: str):
    access_key = os.getenv("CF_R2_ACCESS_KEY_ID")
    secret_key = os.getenv("CF_R2_SECRET_ACCESS_KEY")
    endpoint = os.getenv("CF_R2_ENDPOINT_URL")
    if not access_key or not secret_key:
        raise ValueError("CF_R2_ACCESS_KEY_ID and CF_R2_SECRET_ACCESS_KEY must be set")
    if not endpoint:
        raise ValueError("CF_R2_ENDPOINT_URL must be set")

    endpoint = endpoint.rstrip("/").removesuffix("/" + bucket_name)
    logger.info("Connecting to R2 endpoint %s, bucket %s", endpoint, bucket_name)
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(retries={"max_attempts": 8, "mode": "standard"}),
    )
    try:
        client.head_bucket(Bucket=bucket_name)
        logger.info("Verified access to bucket %s", bucket_name)
    except client.exceptions.NoSuchBucket:
        logger.error("Bucket does not exist: %s", bucket_name)
        raise
    except Exception as exc:
        logger.warning("Could not verify bucket (continuing): %s", exc)
    return client


def list_top_prefixes(client, bucket: str, prefix: str) -> list[str]:
    paginator = client.get_paginator("list_objects_v2")
    found: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
        for item in page.get("CommonPrefixes", []):
            found.append(item["Prefix"])
    return found


def iter_objects(client, bucket: str, prefix: str, limit: int = 0) -> Iterable[dict[str, Any]]:
    paginator = client.get_paginator("list_objects_v2")
    counted = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj
            counted += 1
            if limit and counted >= limit:
                return


def daterange(start: date, end: date) -> list[str]:
    days: list[str] = []
    current = start
    while current <= end:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def parse_iso_date(value: str) -> date | None:
    if not value or value == "unknown":
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def ordered_image_types(found: Iterable[str]) -> list[str]:
    seen = set(found)
    ordered = [name for name in IMAGE_TYPE_ORDER if name in seen]
    ordered.extend(sorted(seen - set(ordered)))
    return ordered


def build_type_columns(stats_map: dict[Any, BucketStats]) -> tuple[list[str], list[str], list[str]]:
    image_types: set[str] = set()
    other_types: set[str] = set()
    for stats in stats_map.values():
        image_types.update(stats.image_types)
        other_types.update(stats.other_types)
    return ordered_image_types(image_types), sorted(other_types), []


def dataframe_from_rows(
    rows: list[dict[str, Any]],
    extra: dict[str, Any],
    image_types: list[str],
    other_types: list[str],
) -> pd.DataFrame:
    columns = list(row_from_stats(BucketStats(), extra, image_types, other_types).keys())
    return pd.DataFrame(rows, columns=columns)


def row_from_stats(
    stats: BucketStats,
    extra: dict[str, Any],
    image_types: list[str],
    other_types: list[str],
) -> dict[str, Any]:
    row = dict(extra)
    row["files"] = stats.total.files
    row["bytes"] = stats.total.bytes
    row["size"] = format_size(stats.total.bytes)
    for group in GROUP_ORDER:
        label = GROUP_LABELS[group]
        counter = stats.groups[group]
        row[f"{label} files"] = counter.files
        row[f"{label} bytes"] = counter.bytes
        row[f"{label} size"] = format_size(counter.bytes)
    for img in image_types:
        counter = stats.image_types[img]
        row[f"{img} files"] = counter.files
        row[f"{img} bytes"] = counter.bytes
        row[f"{img} size"] = format_size(counter.bytes)
    for other in other_types:
        counter = stats.other_types[other]
        row[f"other:{other} files"] = counter.files
        row[f"other:{other} bytes"] = counter.bytes
        row[f"other:{other} size"] = format_size(counter.bytes)
    return row


def overview_rows(stats: BucketStats) -> list[dict[str, Any]]:
    total = max(stats.total.bytes, 1)
    rows: list[dict[str, Any]] = []

    def add(name: str, counter: Counter, indent: bool = False) -> None:
        rows.append(
            {
                "type": ("  " + name) if indent else name,
                "files": counter.files,
                "bytes": counter.bytes,
                "size": format_size(counter.bytes),
                "percent": round(100.0 * counter.bytes / total, 2),
            }
        )

    add("TOTAL", stats.total)
    add("Excel", stats.groups["excel"])
    for name, counter in sorted(stats.excel_types.items()):
        add(name, counter, indent=True)
    add("JSON", stats.groups["json"])
    for name, counter in sorted(stats.json_types.items()):
        add(name, counter, indent=True)
    add("CSV", stats.groups["csv"])
    add("Images (all)", stats.groups["image"])
    for name in ordered_image_types(stats.image_types):
        add(name, stats.image_types[name], indent=True)
    add("Other", stats.groups["other"])
    for name, counter in sorted(stats.other_types.items(), key=lambda kv: -kv[1].bytes):
        add(name, counter, indent=True)
    return rows


def write_excel(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            sheet_name = name[:31]
            frame.to_excel(writer, sheet_name=sheet_name, index=False)
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for column in worksheet.columns:
                col_letter = column[0].column_letter
                max_len = 0
                for cell in column[:80]:
                    max_len = max(max_len, len(str(cell.value or "")))
                worksheet.column_dimensions[col_letter].width = min(max_len + 2, 42)


def markdown_table(frame: pd.DataFrame, columns: list[str] | None = None, limit: int = 40) -> str:
    cols = list(frame.columns) if columns is None else [c for c in columns if c in frame.columns]
    view = frame[cols] if cols else frame
    if view.empty:
        return "_No data._\n"
    clipped = view.head(limit)
    headers = [str(c) for c in clipped.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for _, rec in clipped.iterrows():
        lines.append("| " + " | ".join(str(rec[c]) for c in clipped.columns) + " |")
    if len(view) > limit:
        lines.append(f"| … | {len(view) - limit} more rows in the Excel report |")
    return "\n".join(lines) + "\n"


def compact_columns(image_types: list[str]) -> list[str]:
    cols = ["size", "files", "Excel size", "JSON size", "CSV size", "Images size"]
    cols.extend(f"{img} size" for img in image_types)
    cols.append("Other size")
    return cols


def print_section(title: str, frame: pd.DataFrame, columns: list[str]) -> None:
    logger.info("\n%s\n%s", title, "=" * len(title))
    present = [c for c in columns if c in frame.columns]
    if frame.empty:
        logger.info("No data.")
        return
    with pd.option_context("display.max_rows", 200, "display.max_columns", 40, "display.width", 200):
        logger.info("\n%s", frame[present].to_string(index=False))


def analyze(args: argparse.Namespace) -> int:
    bucket = args.bucket or os.getenv("CF_R2_BUCKET_NAME")
    if not bucket:
        raise ValueError("Bucket name required via --bucket or CF_R2_BUCKET_NAME")

    prefix = (args.prefix or "").lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    client = make_r2_client(bucket)

    scan_prefix = prefix
    if args.website:
        scan_prefix = f"{prefix}{args.website.strip().strip('/')}/"

    top = list_top_prefixes(client, bucket, scan_prefix or prefix)
    logger.info("Top-level folders under prefix %r: %s", scan_prefix or prefix or "/", top or ["(none / objects at this level)"])

    bucket_stats = BucketStats()
    by_website: dict[str, BucketStats] = defaultdict(BucketStats)
    by_day: dict[str, BucketStats] = defaultdict(BucketStats)
    by_website_day: dict[tuple[str, str], BucketStats] = defaultdict(BucketStats)
    by_website_category: dict[tuple[str, str], BucketStats] = defaultdict(BucketStats)

    scanned = 0
    skipped = 0
    logger.info("Listing objects in s3://%s/%s (metadata only, no downloads)", bucket, scan_prefix)

    for obj in iter_objects(client, bucket, scan_prefix, limit=args.limit):
        key = obj["Key"]
        size = int(obj.get("Size") or 0)
        parsed = parse_object_key(key, root_prefix=prefix)
        if parsed is None:
            skipped += 1
            continue
        if args.website and parsed["website"] != args.website.strip().strip("/"):
            skipped += 1
            continue

        group, subtype = classify_extension(parsed["filename"])
        website = parsed["website"]
        day = parsed["date"]
        category = parsed["category"]

        bucket_stats.add(group, subtype, size)
        by_website[website].add(group, subtype, size)
        by_day[day].add(group, subtype, size)
        by_website_day[(website, day)].add(group, subtype, size)
        by_website_category[(website, category)].add(group, subtype, size)

        scanned += 1
        if scanned % 10000 == 0:
            logger.info("Scanned %s objects… current total %s", f"{scanned:,}", format_size(bucket_stats.total.bytes))

    logger.info("Finished listing: %s files, %s skipped, total %s", f"{scanned:,}", skipped, format_size(bucket_stats.total.bytes))

    today = datetime.now(timezone.utc).date()
    known_dates = [d for d in (parse_iso_date(k) for k in by_day) if d is not None]
    day_index: list[str]
    if args.fill_missing_days and known_dates:
        oldest = min(known_dates)
        if args.start_date:
            oldest = max(oldest, datetime.strptime(args.start_date, "%Y-%m-%d").date())
        end = today
        if args.end_date:
            end = datetime.strptime(args.end_date, "%Y-%m-%d").date()
        day_index = daterange(oldest, end)
        for day in day_index:
            _ = by_day[day]
    else:
        day_index = sorted(k for k in by_day if k != "unknown")
        if "unknown" in by_day:
            day_index.append("unknown")

    image_types, other_types, _ = build_type_columns({**by_website, **by_day, "": bucket_stats})

    overview_df = pd.DataFrame(overview_rows(bucket_stats))
    websites_df = dataframe_from_rows(
        [
            row_from_stats(stats, {"website": website}, image_types, other_types)
            for website, stats in sorted(by_website.items(), key=lambda kv: -kv[1].total.bytes)
        ],
        {"website": ""},
        image_types,
        other_types,
    )
    days_df = dataframe_from_rows(
        [
            row_from_stats(by_day[day], {"date": day}, image_types, other_types)
            for day in day_index
        ],
        {"date": ""},
        image_types,
        other_types,
    )
    if "unknown" in by_day and "unknown" not in day_index:
        days_df = pd.concat(
            [
                days_df,
                dataframe_from_rows(
                    [row_from_stats(by_day["unknown"], {"date": "unknown"}, image_types, other_types)],
                    {"date": ""},
                    image_types,
                    other_types,
                ),
            ],
            ignore_index=True,
        )

    website_day_rows = []
    websites_sorted = sorted(by_website)
    for day in day_index:
        for website in websites_sorted:
            stats = by_website_day.get((website, day))
            if stats is None and not args.fill_missing_days:
                continue
            if stats is None:
                stats = BucketStats()
            website_day_rows.append(
                row_from_stats(stats, {"date": day, "website": website}, image_types, other_types)
            )
    website_days_df = dataframe_from_rows(
        website_day_rows,
        {"date": "", "website": ""},
        image_types,
        other_types,
    )

    categories_df = dataframe_from_rows(
        [
            row_from_stats(stats, {"website": website, "category": category}, image_types, other_types)
            for (website, category), stats in sorted(
                by_website_category.items(), key=lambda kv: (kv[0][0], -kv[1].total.bytes)
            )
        ],
        {"website": "", "category": ""},
        image_types,
        other_types,
    )

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    excel_path = output_dir / f"r2-analysis-{stamp}.xlsx"
    json_path = output_dir / f"r2-analysis-{stamp}.json"
    latest_excel = output_dir / "r2-analysis-latest.xlsx"
    latest_json = output_dir / "r2-analysis-latest.json"

    sheets = {
        "Bucket Overview": overview_df,
        "By Website": websites_df,
        "By Day": days_df,
        "By Website and Day": website_days_df,
        "By Category": categories_df,
    }
    write_excel(excel_path, sheets)
    write_excel(latest_excel, sheets)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "bucket": bucket,
        "prefix": prefix or "",
        "website_filter": args.website or "",
        "objects_scanned": scanned,
        "objects_skipped": skipped,
        "bucket_overview": bucket_stats.snapshot(),
        "websites": {name: stats.snapshot() for name, stats in sorted(by_website.items())},
        "days": {day: by_day[day].snapshot() for day in day_index},
        "categories": {
            f"{website}/{category}": stats.snapshot()
            for (website, category), stats in sorted(by_website_category.items())
        },
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    latest_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    logger.info("Wrote %s", excel_path)
    logger.info("Wrote %s", json_path)

    size_cols = compact_columns(image_types)
    print_section("1) Whole bucket", overview_df, ["type", "files", "size", "percent"])
    website_print_cols = ["website"] + size_cols
    print_section("2) By website", websites_df, website_print_cols)
    print_section("3) By day (oldest → today)", days_df, ["date"] + size_cols)
    if not categories_df.empty:
        print_section("Bonus) By website category", categories_df, ["website", "category"] + size_cols)

    if args.github_summary:
        summary_path = Path(args.github_summary)
        lines = [
            f"# R2 storage analysis",
            "",
            f"- Bucket: `{bucket}`",
            f"- Prefix: `{prefix or '(root)'}`",
            f"- Website filter: `{args.website or 'all'}`",
            f"- Objects scanned: `{scanned:,}`",
            f"- Total size: **{format_size(bucket_stats.total.bytes)}**",
            f"- Generated (UTC): `{payload['generated_at_utc']}`",
            "",
            "## 1) Whole bucket",
            markdown_table(overview_df, ["type", "files", "size", "percent"]),
            "## 2) By website",
            markdown_table(websites_df, [c for c in website_print_cols if c in websites_df.columns]),
            "## 3) By day (oldest → today, first 40 rows)",
            markdown_table(days_df, [c for c in (["date"] + size_cols) if c in days_df.columns], limit=40),
            "",
            "Full day-by-day and website×day tables are in the Excel artifact.",
        ]
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        existing = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
        summary_path.write_text(existing + "\n".join(lines) + "\n", encoding="utf-8")
        logger.info("Wrote GitHub step summary to %s", summary_path)

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze Cloudflare R2 storage by type, website, and day")
    parser.add_argument("--bucket", default=os.getenv("CF_R2_BUCKET_NAME"), help="R2 bucket name")
    parser.add_argument(
        "--prefix",
        default="",
        help="Optional key prefix inside the bucket (e.g. data-collection-dl/)",
    )
    parser.add_argument("--website", default="", help="Analyze one website folder only, e.g. 4sale-data")
    parser.add_argument("--output", default="r2-analysis-output", help="Directory for Excel/JSON reports")
    parser.add_argument("--start-date", default="", help="Oldest day to include when filling the calendar (YYYY-MM-DD)")
    parser.add_argument("--end-date", default="", help="Newest day to include (YYYY-MM-DD, default today UTC)")
    parser.add_argument(
        "--fill-missing-days",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include empty days from oldest found date through today",
    )
    parser.add_argument("--limit", type=int, default=0, help="Debug: stop after N objects (0 = all)")
    parser.add_argument("--github-summary", default="", help="Append markdown tables to this file")
    return parser


if __name__ == "__main__":
    try:
        raise SystemExit(analyze(build_parser().parse_args()))
    except Exception as exc:
        logger.exception("R2 analysis failed: %s", exc)
        raise
