"""VerifyBatch: ตรวจว่า batch ครบและไม่ซ้ำ แล้วเขียน trusted/.../_SUCCESS

ตรวจ 4 ข้อ (อ่านจำนวนแถวจาก footer ของ Parquet ใน S3)
  1. raw = trusted + quarantine           (ไม่มีแถวหาย/เกิน)
  2. แถวใน trusted ตรงกับ rows_valid
  3. แถวใน quarantine ตรงกับ rows_invalid (หรือไม่มีไฟล์ถ้าเป็น 0)
  4. ใต้ trusted/.../ มีไฟล์ข้อมูลไฟล์เดียว (ไม่ซ้ำ)  -> รันซ้ำแล้วไม่เกิดไฟล์เพิ่ม
ไม่ผ่าน -> raise BatchVerificationError (ไม่เขียน _SUCCESS จึงรันซ้ำได้)
"""
from common import pipeline as p


def lambda_handler(event, context=None):
    ctx = dict(event)
    if ctx.get("duplicate"):
        return ctx
    p.require(ctx, "bucket", "rows_valid", "rows_invalid")
    bucket = ctx["bucket"]
    problems = []

    raw_rows = p.parquet_num_rows(bucket, p.raw_key(ctx))
    trusted_rows = p.parquet_num_rows(bucket, p.trusted_key(ctx))
    if ctx["rows_invalid"] > 0:
        quarantine_rows = p.parquet_num_rows(bucket, p.quarantine_data_key(ctx))
    else:
        quarantine_rows = 0
        if p.key_exists(bucket, p.quarantine_data_key(ctx)):
            problems.append("พบไฟล์ใน quarantine ทั้งที่ rows_invalid = 0")

    if raw_rows != trusted_rows + quarantine_rows:
        problems.append(f"raw {raw_rows} != trusted {trusted_rows} + quarantine {quarantine_rows}")
    if trusted_rows != ctx["rows_valid"]:
        problems.append(f"trusted {trusted_rows} != rows_valid {ctx['rows_valid']}")
    if quarantine_rows != ctx["rows_invalid"]:
        problems.append(f"quarantine {quarantine_rows} != rows_invalid {ctx['rows_invalid']}")
    data_files = [k for k in p.list_keys(bucket, p.trusted_prefix(ctx)) if k.endswith(".parquet")]
    if len(data_files) != 1:
        problems.append(f"ใต้ trusted ต้องมี 1 ไฟล์ข้อมูล แต่พบ {len(data_files)}: {data_files}")
    if problems:
        raise p.BatchVerificationError(f"batch {ctx['batch_id']} ไม่ผ่านการตรวจ: " + "; ".join(problems))

    p.put_json(bucket, p.success_key(ctx), {
        "batch_id": ctx["batch_id"], "verified_at": p.utc_now_iso(),
        "rows_raw": raw_rows, "rows_trusted": trusted_rows, "rows_quarantine": quarantine_rows,
    })
    ctx.update(status="VERIFIED", verified=True)
    return ctx
