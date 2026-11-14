"""โครงสร้างกลางของ data contract (ใช้ร่วมกันทุกประเภทแท็กซี่)

หลักการ
- Rule = "สิ่งที่ข้อมูลต้องเป็น" (requirement) ไม่ใช่ "สิ่งที่ผิด"
  แถวที่ไม่ผ่านเงื่อนไข = แถวที่ละเมิด (violation)
- ค่า NULL ไม่ถูกนับว่าละเมิด ยกเว้นกฎ op="not_null"
- severity: BLOCK = ส่งเข้า quarantine, WARN = ติดแฟล็กและรายงานแต่ไม่ตัด, INFO = รายงานอย่างเดียว
- กฎทั้งหมดทำงานกับข้อมูลดิบ (ก่อน Standardize)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pyarrow as pa
import pyarrow.compute as pc

BLOCK = "BLOCK"
WARN = "WARN"
INFO = "INFO"

# TLC Taxi Zone ของสนามบิน: 1 = Newark (EWR), 132 = JFK, 138 = LaGuardia (LGA)
AIRPORT_ZONES = frozenset({1, 132, 138})

# op ที่รองรับ
#   gt ge lt le eq ne   : เทียบ column กับค่าคงที่ (value)
#   in                  : column ต้องอยู่ในชุด value
#   not_null            : column ห้ามเป็น NULL
#   le_col / ge_col     : column ต้อง <= / >= คอลัมน์อื่น (value = ชื่อคอลัมน์)
#   implies             : ถ้า column == value[0] แล้ว คอลัมน์ value[1] ต้อง == value[2]
OPS = {"gt", "ge", "lt", "le", "eq", "ne", "in", "not_null", "le_col", "ge_col", "implies"}


@dataclass(frozen=True)
class Rule:
    id: str
    column: str
    op: str
    value: Any
    severity: str
    description: str
    # ใช้กฎนี้เฉพาะแถวที่ PU หรือ DO อยู่ในชุดนี้: (("PULocationID", "DOLocationID"), AIRPORT_ZONES)
    when_any_in: Optional[tuple] = None


def _requirement(table: pa.Table, r: Rule):
    col = table[r.column]
    if r.op == "not_null":
        return pc.is_valid(col)
    if r.op == "gt":
        return pc.greater(col, r.value)
    if r.op == "ge":
        return pc.greater_equal(col, r.value)
    if r.op == "lt":
        return pc.less(col, r.value)
    if r.op == "le":
        return pc.less_equal(col, r.value)
    if r.op == "eq":
        return pc.equal(col, r.value)
    if r.op == "ne":
        return pc.not_equal(col, r.value)
    if r.op == "in":
        value_set = pa.array(sorted(r.value), type=col.type)
        return pc.or_(pc.is_in(col, value_set=value_set), pc.is_null(col))
    if r.op == "le_col":
        return pc.less_equal(col, table[r.value])
    if r.op == "ge_col":
        return pc.greater_equal(col, table[r.value])
    if r.op == "implies":
        if_value, other_col, then_value = r.value
        return pc.or_kleene(
            pc.invert(pc.equal(col, if_value)),
            pc.equal(table[other_col], then_value),
        )
    raise ValueError(f"op ไม่รองรับ: {r.op} (rule {r.id})")


def violation_mask(table: pa.Table, r: Rule):
    """BooleanArray: True = แถวนี้ละเมิดกฎ"""
    violated = pc.fill_null(pc.invert(_requirement(table, r)), False)
    if r.when_any_in is not None:
        columns, zones = r.when_any_in
        hit = None
        for c in columns:
            m = pc.fill_null(pc.is_in(table[c], value_set=pa.array(sorted(zones), type=table[c].type)), False)
            hit = m if hit is None else pc.or_(hit, m)
        violated = pc.and_(violated, hit)
    return violated


def evaluate(table: pa.Table, rules):
    """คืน (counts, block_mask)
    counts     : {rule_id: จำนวนแถวที่ละเมิด}
    block_mask : True = แถวที่ละเมิดกฎ BLOCK อย่างน้อยหนึ่งข้อ (ไป quarantine)
    """
    counts = {}
    block_mask = None
    for r in rules:
        v = violation_mask(table, r)
        counts[r.id] = pc.sum(v.cast(pa.int64())).as_py() or 0
        if r.severity == BLOCK:
            block_mask = v if block_mask is None else pc.or_(block_mask, v)
    return counts, block_mask
