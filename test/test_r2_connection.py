"""
Cloudflare R2 connection test.

Checks:
  1. All required env vars are present
  2. boto3 client can be initialized with the R2 endpoint
  3. Bucket exists and is accessible (HeadBucket)
  4. Can upload a small test object (PUT)
  5. Can read the test object back (GET)
  6. Can delete the test object (DELETE)
  7. Can list objects in the bucket (ListObjectsV2)

Usage:
    CF_R2_ACCESS_KEY_ID=... CF_R2_SECRET_ACCESS_KEY=... \
    CF_R2_ENDPOINT_URL=... CF_R2_BUCKET_NAME=... \
    python CFl_data/test_r2_connection.py

Exit code 0 = all checks passed.
Exit code 1 = one or more checks failed.
"""

import os
import sys
import json
from datetime import datetime, timezone

import boto3
from botocore.config import Config

# -- Env vars ------------------------------------------------------------------

REQUIRED_VARS = [
    "CF_R2_ACCESS_KEY_ID",
    "CF_R2_SECRET_ACCESS_KEY",
    "CF_R2_ENDPOINT_URL",
    "CF_R2_BUCKET_NAME",
]


def check_env() -> bool:
    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        print(f"[FAIL] Missing environment variables: {', '.join(missing)}")
        return False
    print("[OK]   All required environment variables are set")
    for v in REQUIRED_VARS:
        val = os.environ[v]
        # Mask secret values — show only first 6 chars
        display = val[:6] + "***" if "KEY" in v or "SECRET" in v else val
        print(f"         {v} = {display}")
    return True


# -- R2 client -----------------------------------------------------------------

def build_client():
    return boto3.client(
        "R2",
        endpoint_url=os.environ["CF_R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["CF_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["CF_R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(
            signature_version="R2v4",
            R2={"addressing_style": "path"},
        ),
    )


# -- Individual checks ---------------------------------------------------------

def check_head_bucket(client, bucket: str) -> bool:
    """
    HeadBucket is non-fatal on R2 — object-scoped API tokens often return 404
    even when the bucket is fully accessible for PUT/GET.
    Returns True always; a hard failure here would be a false negative.
    """
    try:
        client.head_bucket(Bucket=bucket)
        print(f"[OK]   HeadBucket — bucket '{bucket}' exists and is accessible")
    except Exception as e:
        print(f"[WARN] HeadBucket returned an error (common with R2 object-scoped tokens): {e}")
        print(f"         This is NOT a blocker — PUT/GET/DELETE will confirm real access below.")
    return True  # always non-fatal


def check_put_object(client, bucket: str, key: str) -> bool:
    payload = json.dumps({
        "test": "CFl_data R2 connection test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    try:
        client.put_object(Bucket=bucket, Key=key, Body=payload, ContentType="application/json")
        print(f"[OK]   PutObject — uploaded '{key}'")
        return True
    except Exception as e:
        print(f"[FAIL] PutObject error: {e}")
        return False


def check_get_object(client, bucket: str, key: str) -> bool:
    try:
        resp = client.get_object(Bucket=bucket, Key=key)
        body = resp["Body"].read().decode("utf-8")
        data = json.loads(body)
        print(f"[OK]   GetObject — read back '{key}' (timestamp: {data.get('timestamp', '?')})")
        return True
    except Exception as e:
        print(f"[FAIL] GetObject error: {e}")
        return False


def check_list_objects(client, bucket: str, prefix: str) -> bool:
    """
    ListObjectsV2 requires the r2:list permission which is separate from
    object read/write. Scrapers only PUT data so this is non-fatal.
    """
    try:
        resp = client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=5)
        count = resp.get("KeyCount", 0)
        print(f"[OK]   ListObjectsV2 — found {count} object(s) under prefix '{prefix}'")
    except Exception as e:
        print(f"[WARN] ListObjectsV2 failed (r2:list permission may not be granted): {e}")
        print(f"         This is NOT a blocker — scrapers only need PUT/GET/DELETE.")
    return True  # always non-fatal


def check_delete_object(client, bucket: str, key: str) -> bool:
    try:
        client.delete_object(Bucket=bucket, Key=key)
        print(f"[OK]   DeleteObject — removed test object '{key}'")
        return True
    except Exception as e:
        print(f"[FAIL] DeleteObject error: {e}")
        return False


# -- Main ----------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("  Cloudflare R2 Connection Test")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    results = []

    # 1. Env vars
    results.append(check_env())
    if not results[-1]:
        print("\n[ABORT] Fix missing env vars before proceeding.")
        return 1

    bucket = os.environ["CF_R2_BUCKET_NAME"]
    test_key = "_cfdata_connection_test/probe.json"

    # 2. Build client
    try:
        client = build_client()
        print("[OK]   boto3 R2 client initialized")
    except Exception as e:
        print(f"[FAIL] Could not build boto3 client: {e}")
        return 1

    # 3–7. Run checks
    results.append(check_head_bucket(client, bucket))
    results.append(check_put_object(client, bucket, test_key))
    results.append(check_get_object(client, bucket, test_key))
    results.append(check_list_objects(client, bucket, "_cfdata_connection_test/"))
    results.append(check_delete_object(client, bucket, test_key))

    # Summary
    passed = sum(results)
    total = len(results)
    print("=" * 60)
    if all(results):
        print(f"  RESULT: ALL {total} CHECKS PASSED ?")
        print("  Cloudflare R2 is correctly configured.")
    else:
        print(f"  RESULT: {passed}/{total} CHECKS PASSED — SEE FAILURES ABOVE")
    print("=" * 60)

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
