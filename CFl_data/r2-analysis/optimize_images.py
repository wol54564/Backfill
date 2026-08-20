"""
Download images from R2 for 4sale-data and bleems-data on 2026-08-17,
convert to WebP at 50% quality, and upload copies to:

  optimize/{site}/{year}/{month}/{day}/{relative path}.webp

Example:
  4sale-data/electronics/year=2026/month=08/day=17/images/phones/abc.jpg
    -> optimize/4sale/2026/8/17/electronics/images/phones/abc.webp

Original objects are never modified or deleted.
"""

from __future__ import annotations

import argparse
import io
import logging
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

import boto3
from botocore.config import Config
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("optimize-images")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".avif", ".heic", ".heif", ".ico"}

SOURCE_FOLDERS = {
    "4sale-data": "4sale",
    "bleems-data": "bleems",
}
TARGET_DATE = "2026-08-17"
WEBP_QUALITY = 50
OUTPUT_ROOT = "optimize"


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
        config=Config(retries={"max_attempts": 8, "mode": "standard"}, max_pool_connections=32),
    )


def iter_objects(client, bucket: str, prefix: str):
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj


def is_image(key: str) -> bool:
    return Path(key).suffix.lower() in IMAGE_EXTS


def is_source_image(key: str) -> bool:
    """Skip previous optimizer output and the new optimize/ tree."""
    if key.startswith(f"{OUTPUT_ROOT}/"):
        return False
    if "/optimized/" in key:
        return False
    return is_image(key)


def date_prefixes(client, bucket: str, source: str, year: str, month: str, day: str) -> list[str]:
    """Only list the target day's partitions, not the whole website folder."""
    date_part = f"year={year}/month={month}/day={day}/"
    prefixes = [f"{source}/{date_part}"]

    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=f"{source}/", Delimiter="/"):
        for cp in page.get("CommonPrefixes", []):
            child = cp["Prefix"]
            name = child.rstrip("/").rsplit("/", 1)[-1]
            if name.startswith("year="):
                continue
            prefixes.append(f"{child}{date_part}")
    return prefixes


def optimized_key(original_key: str, source: str, dest_name: str, year: str, month: str, day: str) -> str:
    """
    Map a source key onto optimize/{site}/{Y}/{M}/{D}/...

    Month and day are unpadded (8 not 08) as requested.
    Category and remaining path are kept so filenames do not collide.
    """
    date_part = f"year={year}/month={month}/day={day}/"
    idx = original_key.find(date_part)
    if idx == -1:
        after_source = original_key[len(source):].lstrip("/")
        relative = Path(after_source).with_suffix(".webp").as_posix()
        category = ""
    else:
        before = original_key[:idx].rstrip("/")
        after = original_key[idx + len(date_part):]
        category = before[len(source):].lstrip("/")
        relative = Path(after).with_suffix(".webp").as_posix() if after else Path(original_key).stem + ".webp"

    parts = [OUTPUT_ROOT, dest_name, year, str(int(month)), str(int(day))]
    if category:
        parts.append(category)
    parts.append(relative)
    return "/".join(p for p in parts if p)


def convert_to_webp(img_data: bytes) -> bytes:
    img = Image.open(io.BytesIO(img_data))
    img = img.convert("RGBA") if img.mode in ("RGBA", "LA", "PA") else img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=WEBP_QUALITY)
    return buf.getvalue()


def process_one(client, bucket: str, key: str, new_key: str, skip_existing: bool) -> tuple[str, int, str | None]:
    """
    Returns (status, optimized_bytes, error).
    status is 'uploaded', 'skipped', or 'error'.
    Original object is only read; never overwritten.
    """
    if skip_existing:
        try:
            head = client.head_object(Bucket=bucket, Key=new_key)
            return "skipped", int(head["ContentLength"]), None
        except client.exceptions.ClientError:
            pass

    try:
        response = client.get_object(Bucket=bucket, Key=key)
        img_data = response["Body"].read()
        webp_data = convert_to_webp(img_data)
        client.put_object(
            Bucket=bucket,
            Key=new_key,
            Body=webp_data,
            ContentType="image/webp",
        )
        return "uploaded", len(webp_data), None
    except Exception as exc:
        return "error", 0, str(exc)


def run(args: argparse.Namespace) -> None:
    bucket = args.bucket or os.getenv("CF_R2_BUCKET_NAME")
    if not bucket:
        raise ValueError("Bucket name required via --bucket or CF_R2_BUCKET_NAME")

    client = make_client(bucket)
    year, month, day = TARGET_DATE.split("-")

    stats: dict[str, dict] = defaultdict(lambda: {
        "original_bytes": 0, "optimized_bytes": 0, "count": 0, "errors": 0, "skipped": 0,
    })
    lock = Lock()

    logger.info("Sources : %s", ", ".join(SOURCE_FOLDERS))
    logger.info("Date    : %s", TARGET_DATE)
    logger.info("Output  : %s/{site}/%s/%s/%s/...", OUTPUT_ROOT, year, int(month), int(day))
    logger.info("Original images will not be modified")

    for source, dest_name in SOURCE_FOLDERS.items():
        logger.info("=== Processing %s -> %s/%s/%s/%s/%s ===", source, OUTPUT_ROOT, dest_name, year, int(month), int(day))
        prefixes = date_prefixes(client, bucket, source, year, month, day)
        logger.info("  %d date prefixes to scan", len(prefixes))

        jobs: list[tuple[str, int, str]] = []
        for prefix in prefixes:
            listed = 0
            matched = 0
            for obj in iter_objects(client, bucket, prefix):
                listed += 1
                key = obj["Key"]
                if not is_source_image(key):
                    continue
                size = int(obj.get("Size", 0))
                new_key = optimized_key(key, source, dest_name, year, month, day)
                jobs.append((key, size, new_key))
                matched += 1
            if listed:
                logger.info("  %s : %d objects listed, %d images queued", prefix, listed, matched)

        logger.info("  %s: %d images to convert", source, len(jobs))
        if not jobs:
            continue

        done = 0

        def handle(job: tuple[str, int, str]) -> None:
            nonlocal done
            key, size, new_key = job
            status, opt_bytes, err = process_one(client, bucket, key, new_key, args.skip_existing)
            with lock:
                stats[source]["original_bytes"] += size
                stats[source]["count"] += 1
                if status == "error":
                    stats[source]["errors"] += 1
                    logger.warning("    Failed %s: %s", key, err)
                else:
                    stats[source]["optimized_bytes"] += opt_bytes
                    if status == "skipped":
                        stats[source]["skipped"] += 1
                done += 1
                if done % 50 == 0 or done == len(jobs):
                    logger.info(
                        "    %s: %d/%d images (uploaded/skipped/errors tracked in summary)",
                        source, done, len(jobs),
                    )

        workers = max(1, args.workers)
        if workers == 1:
            for job in jobs:
                handle(job)
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(handle, job) for job in jobs]
                for fut in as_completed(futures):
                    fut.result()

    print("\n" + "=" * 100)
    print(f"{'Source':<20} {'Images':>7} {'Skipped':>8} {'Original':>12} {'WebP 50%':>12} {'Saved':>10} {'Errors':>7}")
    print("-" * 100)

    grand_original = 0
    grand_optimized = 0
    grand_count = 0
    grand_skipped = 0

    for source in SOURCE_FOLDERS:
        s = stats[source]
        orig = s["original_bytes"]
        opt = s["optimized_bytes"]
        cnt = s["count"]
        errs = s["errors"]
        skipped = s["skipped"]
        saved_pct = f"{100 * (1 - opt / orig):.1f}%" if orig > 0 else "N/A"
        print(f"{source:<20} {cnt:>7} {skipped:>8} {format_size(orig):>12} {format_size(opt):>12} {saved_pct:>10} {errs:>7}")
        grand_original += orig
        grand_optimized += opt
        grand_count += cnt
        grand_skipped += skipped

    print("-" * 100)
    total_saved = f"{100 * (1 - grand_optimized / grand_original):.1f}%" if grand_original > 0 else "N/A"
    print(f"{'TOTAL':<20} {grand_count:>7} {grand_skipped:>8} {format_size(grand_original):>12} {format_size(grand_optimized):>12} {total_saved:>10}")
    print("=" * 100)
    print(f"Output prefix: {OUTPUT_ROOT}/4sale/{year}/{int(month)}/{int(day)}/ and {OUTPUT_ROOT}/bleems/{year}/{int(month)}/{int(day)}/")
    print("Originals were not modified.")


def main():
    parser = argparse.ArgumentParser(description="Optimize 4sale/bleems R2 images to WebP 50% quality")
    parser.add_argument("--bucket", default=os.getenv("CF_R2_BUCKET_NAME"), help="R2 bucket name")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="Skip images that already have an optimized version")
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    parser.add_argument("--workers", type=int, default=8, help="Parallel download/convert/upload workers")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
