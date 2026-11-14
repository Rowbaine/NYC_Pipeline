"""TransformFunction: Standardize อย่างเดียว กับแถวที่ผ่าน (valid.parquet) -> trusted/{type}/{year}/{batch_id}/

- drop คอลัมน์ใน DROP_COLUMNS ของประเภทนั้น (green/fhvhv: cbd_congestion_fee)
- fhvhv: แปลงแฟล็ก Y/N เป็น 1/0 (int8) ตาม STANDARDIZE_FLAGS / FLAG_MAP
ไม่ทำ business logic หรือ aggregation
"""
import os

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from common import pipeline as p
from common.contract import get_ruleset


def standardize(table, rs):
    drop = [c for c in getattr(rs, "DROP_COLUMNS", ()) if c in table.column_names]
    if drop:
        table = table.drop_columns(drop)
    flag_map = getattr(rs, "FLAG_MAP", {})
    for name in getattr(rs, "STANDARDIZE_FLAGS", ()):
        if name not in table.column_names:
            continue
        col = table[name]
        converted = pc.if_else(pc.equal(col, "Y"), flag_map["Y"], pc.if_else(pc.equal(col, "N"), flag_map["N"], None))
        out = converted.cast(getattr(rs, "FLAG_DTYPE", "int8"))
        table = table.set_column(table.schema.get_field_index(name), name, out)
    return table


def lambda_handler(event, context=None):
    ctx = dict(event)
    if ctx.get("duplicate"):
        return ctx
    p.require(ctx, "bucket", "taxi_type")
    bucket = ctx["bucket"]
    rs = get_ruleset(ctx["taxi_type"])
    rows = 0
    with p.workdir() as tmp:
        src, dst = os.path.join(tmp, "valid.parquet"), os.path.join(tmp, "out.parquet")
        p.download(bucket, p.valid_key(ctx), src)
        pf = pq.ParquetFile(src)
        writer = None
        try:
            for batch in pf.iter_batches(batch_size=p.BATCH_ROWS):
                table = standardize(pa.Table.from_batches([batch], schema=pf.schema_arrow), rs)
                if writer is None:
                    writer = pq.ParquetWriter(dst, table.schema)
                writer.write_table(table)
                rows += table.num_rows
            if writer is None:  # ไม่มีแถวที่ผ่านเลย: เขียนไฟล์ว่างที่มี schema หลัง standardize
                empty = standardize(pf.schema_arrow.empty_table(), rs)
                writer = pq.ParquetWriter(dst, empty.schema)
                writer.write_table(empty)
        finally:
            if writer is not None:
                writer.close()
        p.upload(bucket, p.trusted_key(ctx), dst)
    ctx.update(trusted_key=p.trusted_key(ctx), rows_trusted=rows, status="TRANSFORMED")
    return ctx
