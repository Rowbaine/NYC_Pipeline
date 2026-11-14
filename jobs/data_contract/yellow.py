"""Data contract: Yellow Taxi (yellow_tripdata_*.parquet)
ตามไฟล์ Data_contract ของ Green ("Yellow คล้ายๆ Green") โดยใช้ชื่อคอลัมน์ของ yellow
"""
from .base import AIRPORT_ZONES, BLOCK, WARN, Rule

TAXI_TYPE = "yellow"

RULES = (
    Rule("YEL-01", "VendorID", "in", frozenset({1, 2, 6}), BLOCK, "VendorID ต้องเป็น 1, 2 หรือ 6"),
    Rule("YEL-02", "tpep_pickup_datetime", "le_col", "tpep_dropoff_datetime", BLOCK, "pickup ต้องไม่มากกว่า dropoff"),
    Rule("YEL-03", "passenger_count", "not_null", None, BLOCK, "passenger_count ห้ามเป็น NULL"),
    Rule("YEL-04", "passenger_count", "ge", 1, BLOCK, "passenger_count ต้อง >= 1 (0 โดน BLOCK)"),
    Rule("YEL-05", "trip_distance", "gt", 0, WARN, "trip_distance ต้อง > 0"),
    Rule("YEL-06", "RatecodeID", "in", frozenset({1, 2, 3, 4, 5, 6, 99}), BLOCK, "RatecodeID ต้องเป็น 1-6 หรือ 99"),
    Rule("YEL-07", "payment_type", "in", frozenset({0, 1, 2, 3, 4, 5, 6}), BLOCK, "payment_type ต้องเป็น 0-6"),
    Rule("YEL-08", "fare_amount", "gt", 0, WARN, "fare_amount ต้อง > 0"),
    Rule("YEL-09", "extra", "ge", 0, BLOCK, "extra ห้ามติดลบ"),
    Rule("YEL-10", "mta_tax", "gt", 0, BLOCK, "mta_tax ต้อง > 0"),
    Rule("YEL-11", "tip_amount", "ge", 0, BLOCK, "tip_amount ห้ามติดลบ"),
    Rule("YEL-12", "tolls_amount", "ge", 0, BLOCK, "tolls_amount ห้ามติดลบ"),
    Rule("YEL-13", "improvement_surcharge", "ge", 0, BLOCK, "improvement_surcharge ห้ามติดลบ"),
    Rule("YEL-14", "total_amount", "gt", 0, BLOCK, "total_amount ต้อง > 0"),
    Rule("YEL-15", "congestion_surcharge", "ge", 0, BLOCK, "congestion_surcharge ห้ามติดลบ"),
    Rule("YEL-16", "Airport_fee", "ge", 0, BLOCK, "Airport_fee ห้ามติดลบ"),
    Rule("YEL-17", "Airport_fee", "ne", 0, WARN, "ถ้า PU หรือ DO เป็นสนามบิน Airport_fee ต้องไม่เป็น 0",
         when_any_in=(("PULocationID", "DOLocationID"), AIRPORT_ZONES)),
)

# กฎ PU == DO ถูกยกเลิก (ปล่อยผ่านปกติ)

# คอลัมน์ที่ต้อง drop ใน TransformFunction พร้อมบันทึกหมายเหตุ (ไม่มีในไฟล์ 2024)
DROP_COLUMNS = ()

# Primary key ที่เสนอใหม่ (รอยืนยัน) ทดสอบกับ 2024-01 แล้วซ้ำ 0 แถว
PRIMARY_KEY = ("VendorID", "tpep_pickup_datetime", "tpep_dropoff_datetime",
               "PULocationID", "DOLocationID", "total_amount")
