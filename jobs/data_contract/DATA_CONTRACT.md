# Data Contract — NYC Taxi Trip Records (ม.ค.–มิ.ย. 2024)

เอกสารนี้อธิบายกฎคุณภาพข้อมูลที่ `ValidateFunction` ใช้กับไฟล์ Parquet ทั้ง 4 ประเภท
กฎจริงอยู่ในโค้ด (`yellow.py`, `green.py`, `fhv.py`, `fhvhv.py`, `base.py` ในโฟลเดอร์เดียวกัน) ตารางกฎในเอกสารนี้สร้างจากโค้ดโดยตรง ถ้าแก้กฎในโค้ดต้องอัปเดตเอกสารนี้ตาม

## 1. หลักการ

| ระดับ (severity) | ความหมาย | สิ่งที่เกิดกับแถวที่ละเมิด |
|---|---|---|
| `BLOCK` | ข้อมูลผิดจนใช้ไม่ได้ | ส่งเข้า quarantine และรายงานใน `report.json` |
| `WARN` | น่าสงสัยแต่ใช้ได้ | ผ่านต่อไป ติดแฟล็กและนับจำนวนใน `report.json` |
| `INFO` | ข้อมูลประกอบ | รายงานอย่างเดียว |


## 2. กฎรายประเภท

Primary key ของแต่ละประเภทอยู่ท้ายตารางกฎของประเภทนั้น เป็น key ที่ใช้แทน PK เดิมใน contract ต้นฉบับ (เช่น `VendorID + pickup + PULocationID`) ซึ่งไม่ unique จริง เก็บในโค้ดเป็น `PRIMARY_KEY` ของแต่ละประเภท แต่ยังไม่ได้บังคับเป็นกฎ


### 2.1 Yellow Taxi

| ID | คอลัมน์ | เงื่อนไขที่ต้องเป็น | ระดับ | ละเมิด 2024-01 |
|---|---|---|---|---|
| `YEL-01` | `VendorID` | VendorID ต้องเป็น 1, 2 หรือ 6 | BLOCK | 0 |
| `YEL-02` | `tpep_pickup_datetime` | pickup ต้องไม่มากกว่า dropoff | BLOCK | 56 |
| `YEL-03` | `passenger_count` | passenger_count ห้ามเป็น NULL | BLOCK | 140,162 |
| `YEL-04` | `passenger_count` | passenger_count ต้อง >= 1 (0 โดน BLOCK) | BLOCK | 31,465 |
| `YEL-05` | `trip_distance` | trip_distance ต้อง > 0 | WARN | 60,371 |
| `YEL-06` | `RatecodeID` | RatecodeID ต้องเป็น 1-6 หรือ 99 | BLOCK | 0 |
| `YEL-07` | `payment_type` | payment_type ต้องเป็น 0-6 | BLOCK | 0 |
| `YEL-08` | `fare_amount` | fare_amount ต้อง > 0 | WARN | 38,341 |
| `YEL-09` | `extra` | extra ห้ามติดลบ | BLOCK | 17,548 |
| `YEL-10` | `mta_tax` | mta_tax ต้อง > 0 | BLOCK | 64,141 |
| `YEL-11` | `tip_amount` | tip_amount ห้ามติดลบ | BLOCK | 102 |
| `YEL-12` | `tolls_amount` | tolls_amount ห้ามติดลบ | BLOCK | 2,035 |
| `YEL-13` | `improvement_surcharge` | improvement_surcharge ห้ามติดลบ | BLOCK | 35,502 |
| `YEL-14` | `total_amount` | total_amount ต้อง > 0 | BLOCK | 35,920 |
| `YEL-15` | `congestion_surcharge` | congestion_surcharge ห้ามติดลบ | BLOCK | 28,825 |
| `YEL-16` | `Airport_fee` | Airport_fee ห้ามติดลบ | BLOCK | 4,921 |
| `YEL-17` | `Airport_fee` | ถ้า PU หรือ DO เป็นสนามบิน Airport_fee ต้องไม่เป็น 0 | WARN | 59,196 |

**Primary key:** `VendorID, tpep_pickup_datetime, tpep_dropoff_datetime, PULocationID, DOLocationID, total_amount` · แถวซ้ำใน 2024-01: 0

### 2.2 Green Taxi

| ID | คอลัมน์ | เงื่อนไขที่ต้องเป็น | ระดับ | ละเมิด 2024-01 |
|---|---|---|---|---|
| `GRN-01` | `VendorID` | VendorID ต้องเป็น 1, 2 หรือ 6 | BLOCK | 0 |
| `GRN-02` | `lpep_pickup_datetime` | pickup ต้องไม่มากกว่า dropoff | BLOCK | 0 |
| `GRN-03` | `passenger_count` | passenger_count ห้ามเป็น NULL | BLOCK | 3,415 |
| `GRN-04` | `passenger_count` | passenger_count ต้อง >= 1 (0 โดน BLOCK) | BLOCK | 512 |
| `GRN-05` | `trip_distance` | trip_distance ต้อง > 0 | WARN | 2,870 |
| `GRN-06` | `RatecodeID` | RatecodeID ต้องเป็น 1-6 หรือ 99 | BLOCK | 0 |
| `GRN-07` | `payment_type` | payment_type ต้องเป็น 0-6 | BLOCK | 0 |
| `GRN-08` | `fare_amount` | fare_amount ต้อง > 0 | WARN | 234 |
| `GRN-09` | `extra` | extra ห้ามติดลบ | BLOCK | 80 |
| `GRN-10` | `mta_tax` | mta_tax ต้อง > 0 | BLOCK | 5,331 |
| `GRN-11` | `tip_amount` | tip_amount ห้ามติดลบ | BLOCK | 9 |
| `GRN-12` | `tolls_amount` | tolls_amount ห้ามติดลบ | BLOCK | 0 |
| `GRN-13` | `improvement_surcharge` | improvement_surcharge ห้ามติดลบ | BLOCK | 182 |
| `GRN-14` | `total_amount` | total_amount ต้อง > 0 | BLOCK | 226 |
| `GRN-15` | `congestion_surcharge` | congestion_surcharge ห้ามติดลบ | BLOCK | 4 |

**Primary key:** `VendorID, lpep_pickup_datetime, lpep_dropoff_datetime, PULocationID, DOLocationID, total_amount` · แถวซ้ำใน 2024-01: 0

### 2.3 FHV (For-Hire Vehicle)

| ID | คอลัมน์ | เงื่อนไขที่ต้องเป็น | ระดับ | ละเมิด 2024-01 |
|---|---|---|---|---|
| `FHV-01` | `pickup_datetime` | pickup ต้องไม่มากกว่า dropoff | BLOCK | 0 |
| `FHV-02` | `SR_Flag` | SR_Flag ต้องเป็น 1 หรือ NULL | INFO | 0 |

**Primary key:** `dispatching_base_num, pickup_datetime, dropOff_datetime, PUlocationID, DOlocationID` · แถวซ้ำใน 2024-01: 2,639

### 2.4 FHVHV (High Volume For-Hire Vehicle)

| ID | คอลัมน์ | เงื่อนไขที่ต้องเป็น | ระดับ | ละเมิด 2024-01 |
|---|---|---|---|---|
| `HVF-01` | `hvfhs_license_num` | hvfhs_license_num ต้องเป็น HV0002 Juno, HV0003 Uber, HV0004 Via หรือ HV0005 Lyft | BLOCK | 0 |
| `HVF-02` | `pickup_datetime` | pickup ต้องไม่มากกว่า dropoff | BLOCK | 0 |
| `HVF-03` | `on_scene_datetime` | on_scene_datetime ต้องไม่น้อยกว่า request_datetime | BLOCK | 135,354 |
| `HVF-04` | `trip_miles` | trip_miles ต้อง > 0 | WARN | 3,286 |
| `HVF-05` | `trip_time` | trip_time ต้อง > 0 | BLOCK | 2 |
| `HVF-06` | `base_passenger_fare` | base_passenger_fare ต้อง > 0 | BLOCK | 7,334 |
| `HVF-07` | `tolls` | tolls ห้ามติดลบ | BLOCK | 0 |
| `HVF-08` | `bcf` | bcf ห้ามติดลบ | BLOCK | 0 |
| `HVF-09` | `sales_tax` | sales_tax ห้ามติดลบ | BLOCK | 0 |
| `HVF-10` | `tips` | tips ห้ามติดลบ | BLOCK | 0 |
| `HVF-11` | `driver_pay` | driver_pay ห้ามติดลบ | BLOCK | 137 |
| `HVF-12` | `airport_fee` | airport_fee ห้ามติดลบ | BLOCK | 0 |
| `HVF-13` | `airport_fee` | ถ้า PU หรือ DO เป็นสนามบิน airport_fee ต้องเป็น 2.5 | WARN | 71,014 |
| `HVF-14` | `shared_match_flag` | shared_match_flag = Y ต้องมี shared_request_flag = Y | BLOCK | 357 |
| `HVF-15` | `wav_match_flag` | wav_match_flag = Y ต้องมี wav_request_flag = Y | WARN | 1,727,864 |

**Primary key:** `hvfhs_license_num, request_datetime, pickup_datetime, dropoff_datetime, PULocationID, DOLocationID` · แถวซ้ำใน 2024-01: 1 (จาก 19.6 ล้านแถว)
