"""IngestFunction: แยกไฟล์จาก incoming/ ไปเก็บที่ raw/{type}/{year}/{batch_id}/ (ไม่แก้ข้อมูล)

รันซ้ำได้: เขียนทับ key เดิม จึงไม่เกิดไฟล์ซ้ำ
"""
from common import pipeline as p


def lambda_handler(event, context=None):
    ctx = dict(event)
    if ctx.get("duplicate"):
        return ctx
    p.require(ctx, "bucket", "source_key", "batch_id", "taxi_type", "year", "filename")
    dst = p.raw_key(ctx)
    p.copy(ctx["bucket"], ctx["source_key"], dst)
    ctx["raw_key"] = dst
    ctx["source_rows"] = p.parquet_num_rows(ctx["bucket"], dst)
    ctx["status"] = "INGESTED"
    return ctx
