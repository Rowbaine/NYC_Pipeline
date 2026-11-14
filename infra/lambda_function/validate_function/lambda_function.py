"""ValidateFunction: ตรวจ data contract ของ raw/ ทีละก้อนของแถว (ไม่โหลดทั้งไฟล์ เพื่อไม่ให้หน่วยความจำเต็ม)

- แถวที่ละเมิดกฎ BLOCK อย่างน้อย 1 ข้อ -> invalid.parquet
- แถวที่เหลือ                          -> valid.parquet
- สรุปจำนวนแถวและจำนวนต่อกฎ            -> report.json
ทั้งสามไฟล์อยู่ใต้ raw/{type}/{year}/{batch_id}/_validated/
"""
import os

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from common import pipeline as p
from common.contract import BLOCK, evaluate, get_ruleset


def lambda_handler(event, context=None):
    ctx = dict(event)
    if ctx.get("duplicate"):
        return ctx
    p.require(ctx, "bucket", "raw_key", "taxi_type")
    bucket = ctx["bucket"]
    rules = get_ruleset(ctx["taxi_type"]).RULES
    counts = {r.id: 0 for r in rules}
    total = valid = invalid = 0

    with p.workdir() as tmp:
        src, valid_path, invalid_path = (os.path.join(tmp, n) for n in ("raw.parquet", "valid.parquet", "invalid.parquet"))
        p.download(bucket, ctx["raw_key"], src)
        pf = pq.ParquetFile(src)
        with pq.ParquetWriter(valid_path, pf.schema_arrow) as vw, pq.ParquetWriter(invalid_path, pf.schema_arrow) as iw:
            for batch in pf.iter_batches(batch_size=p.BATCH_ROWS):
                table = pa.Table.from_batches([batch], schema=pf.schema_arrow)
                batch_counts, block_mask = evaluate(table, rules)
                for rid, n in batch_counts.items():
                    counts[rid] += n
                total += table.num_rows
                if block_mask is None:
                    vw.write_table(table)
                    valid += table.num_rows
                    continue
                bad = table.filter(block_mask)
                good = table.filter(pc.invert(block_mask))
                if bad.num_rows:
                    iw.write_table(bad)
                if good.num_rows:
                    vw.write_table(good)
                invalid += bad.num_rows
                valid += good.num_rows
        p.upload(bucket, p.valid_key(ctx), valid_path)
        p.upload(bucket, p.invalid_key(ctx), invalid_path)

    report = {
        "batch_id": ctx["batch_id"],
        "taxi_type": ctx["taxi_type"],
        "source_key": ctx.get("source_key"),
        "validated_at": p.utc_now_iso(),
        "rows_total": total,
        "rows_valid": valid,
        "rows_invalid": invalid,
        "rules": [
            {"id": r.id, "column": r.column, "severity": r.severity, "violations": counts[r.id], "description": r.description}
            for r in rules
        ],
        "block_rules_violated": sorted(r.id for r in rules if r.severity == BLOCK and counts[r.id] > 0),
    }
    p.put_json(bucket, p.report_key(ctx), report)
    ctx.update(rows_total=total, rows_valid=valid, rows_invalid=invalid, status="VALIDATED")
    return ctx
