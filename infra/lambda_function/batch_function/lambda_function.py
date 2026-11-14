"""BatchFunction: สร้าง batch_id จากไฟล์ใน incoming/ และตรวจ batch ซ้ำ (ต่อประเภท ต่อเดือน)

Input : {"key": "incoming/yellow/yellow_tripdata_2024-01.parquet"} หรือ S3 event, "bucket" (ไม่บังคับ)
Output: ctx ที่มี batch_id, taxi_type, year, month, filename, source_key, bucket, duplicate
        duplicate = True เมื่อ batch นี้ผ่าน VerifyBatch แล้ว (มี trusted/.../_SUCCESS) -> ขั้นต่อไปจะข้าม
"""
from common import pipeline as p


def lambda_handler(event, context=None):
    key, src_bucket = p.extract_source(event)
    ctx = p.parse_source_key(key)
    ctx["bucket"] = p.bucket_name(event, src_bucket)
    if not p.key_exists(ctx["bucket"], key):
        raise p.PipelineError(f"ไม่พบไฟล์ s3://{ctx['bucket']}/{key}")
    ctx["duplicate"] = p.key_exists(ctx["bucket"], p.success_key(ctx))
    ctx["status"] = "DUPLICATE" if ctx["duplicate"] else "NEW"
    return ctx
