"""QuarantineFunction: ถ้ามีแถวที่ไม่ผ่าน ย้ายสำเนา invalid.parquet + report.json ไป quarantine/{type}/{year}/{batch_id}/

ไม่มีแถวที่ไม่ผ่าน -> ไม่สร้างอะไรใน quarantine/ (rows_quarantined = 0)
"""
from common import pipeline as p


def lambda_handler(event, context=None):
    ctx = dict(event)
    if ctx.get("duplicate"):
        return ctx
    p.require(ctx, "bucket", "rows_invalid")
    bucket = ctx["bucket"]
    if ctx["rows_invalid"] > 0:
        p.copy(bucket, p.invalid_key(ctx), p.quarantine_data_key(ctx))
        p.copy(bucket, p.report_key(ctx), p.quarantine_report_key(ctx))
        ctx["quarantine_prefix"] = p.quarantine_prefix(ctx)
    ctx["rows_quarantined"] = ctx["rows_invalid"]
    ctx["status"] = "QUARANTINED" if ctx["rows_invalid"] else "NO_QUARANTINE"
    return ctx
