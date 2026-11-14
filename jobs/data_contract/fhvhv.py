"""Data contract: High Volume FHV (fhvhv_tripdata_*.parquet)
หมายเหตุชื่อคอลัมน์: ไฟล์จริงใช้ trip_miles, tips, request_datetime
กฎทั้งหมดทำงานกับค่า Y/N ดิบ (ก่อน Standardize flag เป็น 1/0)
"""
from .base import AIRPORT_ZONES, BLOCK, WARN, Rule

TAXI_TYPE = "fhvhv"

RULES = (
    Rule("HVF-01", "hvfhs_license_num", "in", frozenset({"HV0002", "HV0003", "HV0004", "HV0005"}), BLOCK,
         "hvfhs_license_num ต้องเป็น HV0002 Juno, HV0003 Uber, HV0004 Via หรือ HV0005 Lyft"),
    Rule("HVF-02", "pickup_datetime", "le_col", "dropoff_datetime", BLOCK, "pickup ต้องไม่มากกว่า dropoff"),
    Rule("HVF-03", "on_scene_datetime", "ge_col", "request_datetime", BLOCK, "on_scene_datetime ต้องไม่น้อยกว่า request_datetime"),
    Rule("HVF-04", "trip_miles", "gt", 0, WARN, "trip_miles ต้อง > 0"),
    Rule("HVF-05", "trip_time", "gt", 0, BLOCK, "trip_time ต้อง > 0"),
    Rule("HVF-06", "base_passenger_fare", "gt", 0, BLOCK, "base_passenger_fare ต้อง > 0"),
    Rule("HVF-07", "tolls", "ge", 0, BLOCK, "tolls ห้ามติดลบ"),
    Rule("HVF-08", "bcf", "ge", 0, BLOCK, "bcf ห้ามติดลบ"),
    Rule("HVF-09", "sales_tax", "ge", 0, BLOCK, "sales_tax ห้ามติดลบ"),
    Rule("HVF-10", "tips", "ge", 0, BLOCK, "tips ห้ามติดลบ"),
    Rule("HVF-11", "driver_pay", "ge", 0, BLOCK, "driver_pay ห้ามติดลบ"),
    Rule("HVF-12", "airport_fee", "ge", 0, BLOCK, "airport_fee ห้ามติดลบ"),
    Rule("HVF-13", "airport_fee", "eq", 2.5, WARN, "ถ้า PU หรือ DO เป็นสนามบิน airport_fee ต้องเป็น 2.5",
         when_any_in=(("PULocationID", "DOLocationID"), AIRPORT_ZONES)),
    Rule("HVF-14", "shared_match_flag", "implies", ("Y", "shared_request_flag", "Y"), BLOCK,
         "shared_match_flag = Y ต้องมี shared_request_flag = Y"),
    Rule("HVF-15", "wav_match_flag", "implies", ("Y", "wav_request_flag", "Y"), WARN,
         "wav_match_flag = Y ต้องมี wav_request_flag = Y"),
)

# กฎ PU == DO ถูกยกเลิก (ปล่อยผ่านปกติ)

# Standardize ใน TransformFunction: แปลง flag Y/N เป็น 1/0
STANDARDIZE_FLAGS = ("shared_request_flag", "shared_match_flag", "access_a_ride_flag",
                     "wav_request_flag", "wav_match_flag")
FLAG_MAP = {"Y": 1, "N": 0}
FLAG_DTYPE = "int8"

# cbd_congestion_fee: ไม่มีในไฟล์ 2024 ให้ drop ใน TransformFunction ถ้าพบ พร้อมบันทึกหมายเหตุ
DROP_COLUMNS = ("cbd_congestion_fee",)
DROP_NOTE = "cbd_congestion_fee ถูก drop ใน Transform (ไม่ใช้ตอบโจทย์ และไฟล์ 2024 ไม่มีคอลัมน์นี้)"

# Primary key ที่เสนอใหม่ (รอยืนยัน) ทดสอบกับ 2024-01 แล้วซ้ำ 1 แถวจาก 19.6 ล้านแถว
PRIMARY_KEY = ("hvfhs_license_num", "request_datetime", "pickup_datetime", "dropoff_datetime",
               "PULocationID", "DOLocationID")
