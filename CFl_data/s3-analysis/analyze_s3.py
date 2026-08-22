"""
Analyze AWS S3 storage by file type, website, and day.

Does not download objects — only lists keys and sizes.

Expected layout (Hive-style dates):
  {website}/{category?}/year=YYYY/month=MM/day=DD/...

Examples (bucket = data-collection-dl):
  4sale-data/animals/year=2026/month=08/day=01/listings.xlsx
  bleems-data/year=2026/month=08/day=01/data.json

Environment variables:
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  S3_BUCKET_NAME
  AWS_DEFAULT_REGION (optional, default us-east-1)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import boto3
from botocore.config import Config

# Allow running as a script: python CFl_data/s3-analysis/analyze_s3.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage_analysis.core import AnalysisOptions, run_analysis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("s3-analysis")

DEFAULT_REGION = "us-east-1"


def resolve_region(explicit: str = "") -> str:
    """Return a non-empty AWS region (GitHub may set env vars to blank strings)."""
    for candidate in (explicit, os.getenv("AWS_DEFAULT_REGION"), os.getenv("AWS_REGION"), DEFAULT_REGION):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return DEFAULT_REGION


def make_s3_client(bucket_name: str, region: str):
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    if not access_key or not secret_key:
        raise ValueError("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set")

    logger.info("Connecting to AWS S3 region %s, bucket %s", region, bucket_name)
    client = boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
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


def analyze(args: argparse.Namespace) -> int:
    bucket = args.bucket or os.getenv("S3_BUCKET_NAME")
    if not bucket:
        raise ValueError("Bucket name required via --bucket or S3_BUCKET_NAME")

    region = resolve_region(args.region)
    client = make_s3_client(bucket, region)

    prefix = (args.prefix or "").lstrip("/")
    options = AnalysisOptions(
        bucket=bucket,
        prefix=prefix,
        website=args.website or "",
        output=args.output,
        start_date=args.start_date or "",
        end_date=args.end_date or "",
        fill_missing_days=args.fill_missing_days,
        limit=args.limit,
        github_summary=args.github_summary or "",
        provider_label="S3",
    )
    return run_analysis(client, options)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze AWS S3 storage by type, website, and day",
    )
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET_NAME"), help="S3 bucket name")
    parser.add_argument(
        "--prefix",
        default="",
        help="Optional key prefix inside the bucket (leave empty if websites are at bucket root)",
    )
    parser.add_argument("--website", default="", help="Analyze one website folder only, e.g. 4sale-data")
    parser.add_argument("--region", default="", help="AWS region (default: AWS_DEFAULT_REGION or us-east-1)")
    parser.add_argument("--output", default="s3-analysis-output", help="Directory for Excel/JSON reports")
    parser.add_argument(
        "--start-date",
        default="",
        help="Oldest day to include when filling the calendar (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        default="",
        help="Newest day to include (YYYY-MM-DD, default today UTC)",
    )
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
        logger.exception("S3 analysis failed: %s", exc)
        raise
