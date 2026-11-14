"""ตัวช่วยกลางที่ Lambda ทุกตัวใช้ร่วมกัน

- แปลงชื่อไฟล์ใน incoming/ เป็นข้อมูล batch
- สร้าง key ของ S3 ในแต่ละโซน
- ฟังก์ชันอ่าน/เขียน S3 ด้วย boto3

โครงสร้างใน S3 (bucket เดียว) batch_id = {type}_{YYYY-MM} เช่น yellow_2024-01
  incoming/{file}.parquet                              ไฟล์ที่เข้ามา (วางตรงๆ ไม่แยกประเภท; รับ incoming/{type}/{file} ด้วย)
  raw/{type}/{year}/{batch_id}/{file}.parquet          ผลของ IngestFunction
  raw/{type}/{year}/{batch_id}/_validated/             ผลของ ValidateFunction (valid.parquet, invalid.parquet, report.json)
  trusted/{type}/{year}/{batch_id}/{file}.parquet      ผลของ TransformFunction (+ _SUCCESS จาก VerifyBatch)
  quarantine/{type}/{year}/{batch_id}/                 แถวที่ไม่ผ่าน (invalid.parquet, report.json)
  curated/{type}/{year}/{batch_id}/{file}.parquet      สำเนาจาก trusted หลังผ่าน VerifyBatch
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import unquote_plus

TAXI_TYPES = ("yellow", "green", "fhv", "fhvhv")
INCOMING, RAW, TRUSTED, CURATED, QUARANTINE = "incoming", "raw", "trusted", "curated", "quarantine"
TMP_DIR = os.environ.get("TMP_DIR", "/tmp")
BATCH_ROWS = int(os.environ.get("BATCH_ROWS", "500000"))  # จำนวนแถวต่อรอบที่อ่านจาก Parquet

_SOURCE_RE = re.compile(r"^(?P<type>yellow|green|fhv|fhvhv)_tripdata_(?P<year>\d{4})-(?P<month>\d{2})\.parquet$")


class PipelineError(Exception):
    """ข้อมูลนำเข้าหรือสถานะของ pipeline ไม่ถูกต้อง"""


class BatchVerificationError(PipelineError):
    """VerifyBatch ตรวจแล้วข้อมูลของ batch ไม่ครบหรือไม่สอดคล้องกัน"""


# ---------------------------------------------------------------- batch / key
def require(ctx: dict, *names: str) -> None:
    missing = [n for n in names if ctx.get(n) in (None, "")]
    if missing:
        raise PipelineError(f"event ขาดฟิลด์ที่จำเป็น: {', '.join(missing)}")


def extract_source(event: dict):
    """คืน (key, bucket หรือ None) จาก event แบบ {"key": ...} หรือ S3 event notification"""
    if event.get("key"):
        return event["key"], event.get("bucket")
    records = event.get("Records") or []
    if records and "s3" in records[0]:
        s3_info = records[0]["s3"]
        return unquote_plus(s3_info["object"]["key"]), s3_info.get("bucket", {}).get("name")
    raise PipelineError('event ต้องมี "key" (เช่น incoming/yellow_tripdata_2024-01.parquet) หรือเป็น S3 event')


def parse_source_key(key: str) -> dict:
    """incoming/yellow_tripdata_2024-01.parquet (หรือ incoming/yellow/yellow_tripdata_2024-01.parquet) -> ข้อมูล batch"""
    parts = key.split("/")
    if parts[0] != INCOMING or len(parts) not in (2, 3):
        raise PipelineError(f"key ต้องอยู่ในรูป incoming/<file>.parquet หรือ incoming/<type>/<file>.parquet : {key}")
    folder, filename = (parts[1] if len(parts) == 3 else None), parts[-1]
    m = _SOURCE_RE.match(filename)
    if not m:
        raise PipelineError(f"ชื่อไฟล์ไม่ตรงรูปแบบ <type>_tripdata_YYYY-MM.parquet : {filename}")
    if folder is not None and m["type"] != folder:
        raise PipelineError(f"โฟลเดอร์ ({folder}) ไม่ตรงกับประเภทในชื่อไฟล์ ({m['type']})")
    month = int(m["month"])
    if not 1 <= month <= 12:
        raise PipelineError(f"เดือนไม่ถูกต้องในชื่อไฟล์: {filename}")
    return {
        "batch_id": f"{m['type']}_{m['year']}-{m['month']}",
        "taxi_type": m["type"],
        "year": m["year"],
        "month": m["month"],
        "filename": filename,
        "source_key": key,
    }


def _partition(ctx: dict) -> str:
    require(ctx, "taxi_type", "year", "batch_id")
    return f"{ctx['taxi_type']}/{ctx['year']}/{ctx['batch_id']}"


def raw_key(ctx):                return f"{RAW}/{_partition(ctx)}/{ctx['filename']}"
def staging_prefix(ctx):         return f"{RAW}/{_partition(ctx)}/_validated/"
def valid_key(ctx):              return staging_prefix(ctx) + "valid.parquet"
def invalid_key(ctx):            return staging_prefix(ctx) + "invalid.parquet"
def report_key(ctx):             return staging_prefix(ctx) + "report.json"
def trusted_prefix(ctx):         return f"{TRUSTED}/{_partition(ctx)}/"
def trusted_key(ctx):            return trusted_prefix(ctx) + ctx["filename"]
def success_key(ctx):            return trusted_prefix(ctx) + "_SUCCESS"
def curated_prefix(ctx):         return f"{CURATED}/{_partition(ctx)}/"
def curated_key(ctx):            return curated_prefix(ctx) + ctx["filename"]
def quarantine_prefix(ctx):      return f"{QUARANTINE}/{_partition(ctx)}/"
def quarantine_data_key(ctx):    return quarantine_prefix(ctx) + "invalid.parquet"
def quarantine_report_key(ctx):  return quarantine_prefix(ctx) + "report.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def workdir():
    """โฟลเดอร์ชั่วคราวใน /tmp ที่ลบทิ้งเมื่อจบ (Lambda ใช้ /tmp ซ้ำระหว่างการเรียก)"""
    path = tempfile.mkdtemp(dir=TMP_DIR)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# ------------------------------------------------------------------------- S3
_client = None


def s3():
    global _client
    if _client is None:
        import boto3

        _client = boto3.client("s3")
    return _client


def reset_client() -> None:
    """ใช้ในการทดสอบเพื่อสร้าง client ใหม่"""
    global _client
    _client = None


def bucket_name(event: dict, from_source: str | None = None) -> str:
    name = event.get("bucket") or from_source or os.environ.get("BUCKET_NAME")
    if not name:
        raise PipelineError('ไม่ทราบชื่อ bucket: ใส่ "bucket" ใน event หรือตั้งตัวแปร BUCKET_NAME')
    return name


def key_exists(bucket: str, key: str) -> bool:
    from botocore.exceptions import ClientError

    try:
        s3().head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def list_keys(bucket: str, prefix: str) -> list[str]:
    keys = []
    for page in s3().get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        keys.extend(o["Key"] for o in page.get("Contents", []))
    return keys


def download(bucket: str, key: str, local_path: str) -> None:
    s3().download_file(bucket, key, local_path)


def upload(bucket: str, key: str, local_path: str) -> None:
    s3().upload_file(local_path, bucket, key)


def copy(bucket: str, src_key: str, dst_key: str) -> None:
    s3().copy({"Bucket": bucket, "Key": src_key}, bucket, dst_key)


def delete_key(bucket: str, key: str) -> None:
    s3().delete_object(Bucket=bucket, Key=key)


def put_json(bucket: str, key: str, obj: dict) -> None:
    body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    s3().put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")


def get_json(bucket: str, key: str) -> dict:
    return json.loads(s3().get_object(Bucket=bucket, Key=key)["Body"].read())


def parquet_num_rows(bucket: str, key: str) -> int:
    """จำนวนแถวของไฟล์ Parquet ใน S3 โดยอ่านเฉพาะส่วนท้ายไฟล์ (footer) ไม่ต้องโหลดทั้งไฟล์"""
    import pyarrow as pa
    import pyarrow.parquet as pq

    size = s3().head_object(Bucket=bucket, Key=key)["ContentLength"]
    if size < 12:
        raise PipelineError(f"ไม่ใช่ไฟล์ Parquet (เล็กเกินไป): s3://{bucket}/{key}")
    tail_len = min(size, 64 * 1024)
    while True:
        tail = s3().get_object(Bucket=bucket, Key=key, Range=f"bytes={size - tail_len}-{size - 1}")["Body"].read()
        if tail[-4:] != b"PAR1":
            raise PipelineError(f"ไม่ใช่ไฟล์ Parquet: s3://{bucket}/{key}")
        footer_len = int.from_bytes(tail[-8:-4], "little")
        if footer_len + 8 <= len(tail) or tail_len >= size:
            break
        tail_len = min(size, footer_len + 8)
    return pq.ParquetFile(pa.BufferReader(tail)).metadata.num_rows
