"""Data contract: Green Taxi (green_tripdata_*.parquet)
หมายเหตุชื่อคอลัมน์: ใน Data_contract เขียน tpep_* แต่ไฟล์ green จริงใช้ lpep_*
"""
from .base import BLOCK, WARN, Rule

TAXI_TYPE = "green"

RULES = (
    Rule("GRN-01", "VendorID", "in", frozenset({1, 2, 6}), BLOCK, "VendorID ต้องเป็น 1, 2 หรือ 6"),
    Rule("GRN-02", "lpep_pickup_datetime", "le_col", "lpep_dropoff_datetime", BLOCK, "pickup ต้องไม่มากกว่า dropoff"),
    Rule("GRN-03", "passenger_count", "not_null", None, BLOCK, "passenger_count ห้ามเป็น NULL"),
    Rule("GRN-04", "passenger_count", "ge", 1, BLOCK, "passenger_count ต้อง >= 1 (0 โดน BLOCK)"),
    Rule("GRN-05", "trip_distance", "gt", 0, WARN, "trip_distance ต้อง > 0"),
    Rule("GRN-06", "RatecodeID", "in", frozenset({1, 2, 3, 4, 5, 6, 99}), BLOCK, "RatecodeID ต้องเป็น 1-6 หรือ 99"),
    Rule("GRN-07", "payment_type", "in", frozenset({0, 1, 2, 3, 4, 5, 6}), BLOCK, "payment_type ต้องเป็น 0-6"),
    Rule("GRN-08", "fare_amount", "gt", 0, WARN, "fare_amount ต้อง > 0"),
    Rule("GRN-09", "extra", "ge", 0, BLOCK, "extra ห้ามติดลบ"),
    Rule("GRN-10", "mta_tax", "gt", 0, BLOCK, "mta_tax ต้อง > 0"),
    Rule("GRN-11", "tip_amount", "ge", 0, BLOCK, "tip_amount ห้ามติดลบ"),
    Rule("GRN-12", "tolls_amount", "ge", 0, BLOCK, "tolls_amount ห้ามติดลบ"),
    Rule("GRN-13", "improvement_surcharge", "ge", 0, BLOCK, "improvement_surcharge ห้ามติดลบ"),
    Rule("GRN-14", "total_amount", "gt", 0, BLOCK, "total_amount ต้อง > 0"),
    Rule("GRN-15", "congestion_surcharge", "ge", 0, BLOCK, "congestion_surcharge ห้ามติดลบ"),
)

# ไม่มีกฎ airport_fee เพราะ green ไม่มีคอลัมน์นี้ในไฟล์ 2024
# กฎ PU == DO ถูกยกเลิก (ปล่อยผ่านปกติ)

# cbd_congestion_fee: ไม่มีในไฟล์ 2024 ให้ drop ใน TransformFunction ถ้าพบ พร้อมบันทึกหมายเหตุ
DROP_COLUMNS = ("cbd_congestion_fee",)
DROP_NOTE = "cbd_congestion_fee ถูก drop ใน Transform (ไม่ใช้ตอบโจทย์ และไฟล์ 2024 ไม่มีคอลัมน์นี้)"

# Primary key ที่เสนอใหม่ (รอยืนยัน) ทดสอบกับ 2024-01 แล้วซ้ำ 0 แถว
PRIMARY_KEY = ("VendorID", "lpep_pickup_datetime", "lpep_dropoff_datetime",
               "PULocationID", "DOLocationID", "total_amount")
