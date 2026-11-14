"""Data contract: FHV (fhv_tripdata_*.parquet)
หมายเหตุชื่อคอลัมน์: ไฟล์จริงใช้ pickup_datetime และ dropOff_datetime (O ใหญ่)
"""
from .base import BLOCK, INFO, Rule

TAXI_TYPE = "fhv"

RULES = (
    Rule("FHV-01", "pickup_datetime", "le_col", "dropOff_datetime", BLOCK, "pickup ต้องไม่มากกว่า dropoff"),
    # SR_Flag เป็น NULL 100% ใน 2024-01 ผ่านเสมอ ไม่มีผลต่อการตัดสินใจ จึงเป็น INFO
    Rule("FHV-02", "SR_Flag", "in", frozenset({1}), INFO, "SR_Flag ต้องเป็น 1 หรือ NULL"),
)

# กฎ PU == DO ถูกยกเลิก (ปล่อยผ่านปกติ)

DROP_COLUMNS = ()

# ไม่ unique: 2024-01 ซ้ำ 2,639 แถว และ PUlocationID/DOlocationID มี NULL
PRIMARY_KEY = ("dispatching_base_num", "pickup_datetime", "dropOff_datetime",
               "PUlocationID", "DOlocationID")
