"""
Download images from R2 for the last 2 partitions, convert to WebP at 50% quality,
upload to new folders in R2 (originals are kept), and report total sizes.

New path layout:
  {website}/{category}/year=YYYY/month=MM/day=DD/optimized/{stem}.webp

Usage:
  python optimize_images.py --bucket <bucket>
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import re
from collections import defaultdict
from pathlib import Path

import boto3
from botocore.config import Config
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("optimize-images")

DATE_RE = re.compile(r"year=(\d{4})/month=(\d{2})/day=(\d{2})")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".avif", ".heic", ".heif", ".ico"}
TARGET_DATES = ["2026-08-17", "2026-08-18"]
WEBP_QUALITY = 50


def format_size(num_bytes: int | float) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024.0 or unit == "TB":
            return f"{value:.2f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024.0
    return f"{value:.2f} TB"


def make_client(bucket: str):
    access_key = os.getenv("CF_R2_ACCESS_KEY_ID")
    secret_key = os.getenv("CF_R2_SECRET_ACCESS_KEY")
    endpoint = os.getenv("CF_R2_ENDPOINT_URL")
    if not all([access_key, secret_key, endpoint]):
        raise ValueError("CF_R2_ACCESS_KEY_ID, CF_R2_SECRET_ACCESS_KEY, CF_R2_ENDPOINT_URL must be set")
    endpoint = endpoint.rstrip("/").removesuffix("/" + bucket)
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(retries={"max_attempts": 8, "mode": "standard"}),
    )


def iter_objects(client, bucket: str, prefix: str):
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj


def extract_date(key: str) -> str | None:
    m = DATE_RE.search(key)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def is_image(key: str) -> bool:
    return Path(key).suffix.lower() in IMAGE_EXTS


def optimized_key(original_key: str) -> str:
    """Insert 'optimized/' before the filename and change extension to .webp."""
    parts = original_key.rsplit("/", 1)
    stem = Path(parts[-1]).stem
    if len(parts) == 2:
        return f"{parts[0]}/optimized/{stem}.webp"
    return f"optimized/{stem}.webp"


def extract_website(key: str) -> str:
    return key.split("/")[0] if "/" in key else "(root)"


def run(args: argparse.Namespace) -> None:
    bucket = args.bucket or os.getenv("CF_R2_BUCKET_NAME")
    if not bucket:
        raise ValueError("Bucket name required via --bucket or CF_R2_BUCKET_NAME")

    client = make_client(bucket)

    # Stats: (website, date) -> {original_bytes, optimized_bytes, count}
    stats: dict[tuple[str, str], dict] = defaultdict(lambda: {
        "original_bytes": 0, "optimized_bytes": 0, "count": 0, "errors": 0
    })

    for target_date in TARGET_DATES:
        y, m, d = target_date.split("-")
        date_prefix = f"year={y}/month={m}/day={d}"
        logger.info("=== Processing date: %s ===", target_date)

        # List all top-level website prefixes
        paginator = client.get_paginator("list_objects_v2")
        top_prefixes = []
        for page in paginator.paginate(Bucket=bucket, Prefix="", Delimiter="/"):
            for cp in page.get("CommonPrefixes", []):
                top_prefixes.append(cp["Prefix"])

        for website_prefix in sorted(top_prefixes):
            website = website_prefix.rstrip("/")
            logger.info("  Scanning %s for %s ...", website, target_date)
            found = 0

            for obj in iter_objects(client, bucket, website_prefix):
                key = obj["Key"]
                obj_date = extract_date(key)
                if obj_date != target_date:
                    continue
                if not is_image(key):
                    continue

                size = int(obj.get("Size", 0))
                stat_key = (website, target_date)
                stats[stat_key]["original_bytes"] += size
                stats[stat_key]["count"] += 1
                found += 1

                new_key = optimized_key(key)

                # Check if already optimized
                if args.skip_existing:
                    try:
                        client.head_object(Bucket=bucket, Key=new_key)
                        logger.debug("    Already exists: %s", new_key)
                        # Still count the optimized size
                        head = client.head_object(Bucket=bucket, Key=new_key)
                        stats[stat_key]["optimized_bytes"] += head["ContentLength"]
                        continue
                    except client.exceptions.ClientError:
                        pass

                try:
                    response = client.get_object(Bucket=bucket, Key=key)
                    img_data = response["Body"].read()

                    img = Image.open(io.BytesIO(img_data))
                    img = img.convert("RGBA") if img.mode in ("RGBA", "LA", "PA") else img.convert("RGB")

                    buf = io.BytesIO()
                    img.save(buf, format="WEBP", quality=WEBP_QUALITY)
                    webp_data = buf.getvalue()

                    client.put_object(
                        Bucket=bucket,
                        Key=new_key,
                        Body=webp_data,
                        ContentType="image/webp",
                    )
                    stats[stat_key]["optimized_bytes"] += len(webp_data)

                    if found % 50 == 0:
                        logger.info("    Processed %d images so far for %s/%s", found, website, target_date)

                except Exception as exc:
                    stats[stat_key]["errors"] += 1
                    logger.warning("    Failed to convert %s: %s", key, exc)

            if found:
                logger.info("    %s: %d images found for %s", website, found, target_date)

    # Print summary
    print("\n" + "=" * 90)
    print(f"{'Website':<35} {'Date':<12} {'Images':>7} {'Original':>12} {'WebP 50%':>12} {'Saved':>10} {'Errors':>7}")
    print("-" * 90)

    grand_original = 0
    grand_optimized = 0
    grand_count = 0

    for (website, dt) in sorted(stats.keys()):
        s = stats[(website, dt)]
        orig = s["original_bytes"]
        opt = s["optimized_bytes"]
        cnt = s["count"]
        errs = s["errors"]
        saved_pct = f"{100 * (1 - opt / orig):.1f}%" if orig > 0 else "N/A"
        print(f"{website:<35} {dt:<12} {cnt:>7} {format_size(orig):>12} {format_size(opt):>12} {saved_pct:>10} {errs:>7}")
        grand_original += orig
        grand_optimized += opt
        grand_count += cnt

    print("-" * 90)
    total_saved = f"{100 * (1 - grand_optimized / grand_original):.1f}%" if grand_original > 0 else "N/A"
    print(f"{'TOTAL':<35} {'':>12} {grand_count:>7} {format_size(grand_original):>12} {format_size(grand_optimized):>12} {total_saved:>10}")
    print("=" * 90)


def main():
    parser = argparse.ArgumentParser(description="Optimize R2 images to WebP 50% quality")
    parser.add_argument("--bucket", default=os.getenv("CF_R2_BUCKET_NAME"), help="R2 bucket name")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="Skip images that already have an optimized version")
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
