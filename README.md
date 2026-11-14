# NYC Taxi — Trip Records (ม.ค.–มิ.ย. 2024)

## 1. คำถาม

**Which taxi type was the most used in the first half of 2024?**
(ประเภทแท็กซี่ใดถูกใช้มากที่สุดในครึ่งปีแรกของ 2024)


## 2. แหล่งที่มาข้อมูล

- **NYC Taxi & Limousine Commission (TLC) — Trip Record Data**
  https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
- รูปแบบไฟล์: Parquet รายเดือน ตั้งชื่อ `{type}_tripdata_{YYYY-MM}.parquet`
- คำอธิบายฟิลด์ (Data Dictionary) อยู่ใน `docs/Dictionary/` (yellow, green, fhv, hvfhs)
- ไฟล์ข้อมูลอยู่ใน `data/{type}/` และโฟลเดอร์ `data/` ถูก ignore ด้วย `.gitignore`

| ประเภท | ความหมาย | จำนวนไฟล์ | เดือนที่มี | จำนวนแถวรวม |
|---|---|---|---|---|
| `yellow` | Yellow Taxi | 6 | 2024-01 ถึง 2024-06 | 20,332,093 |
| `green` | Green Taxi | **5** | 2024-01 ถึง 2024-05 (**ขาด 2024-06**) | 285,059 |
| `fhv` | For-Hire Vehicle | 6 | 2024-01 ถึง 2024-06 | 8,119,228 |
| `fhvhv` | High Volume For-Hire Vehicle (เช่น Uber, Lyft) | 6 | 2024-01 ถึง 2024-06 | 120,864,668 |

ตัวเลขแถวอ่านจาก metadata ของไฟล์ Parquet และ schema ของแต่ละประเภทเหมือนกันทุกเดือน

## 3. Schema ของ Parquet (Input)

### 3.1 Yellow (19 คอลัมน์)

| คอลัมน์ | ชนิด | คำอธิบาย |
|---|---|---|
| `VendorID` | `int32` | รหัสผู้ให้บริการระบบบันทึก trip |
| `tpep_pickup_datetime` | `timestamp[us]` | เวลารับผู้โดยสาร |
| `tpep_dropoff_datetime` | `timestamp[us]` | เวลาส่งผู้โดยสาร |
| `passenger_count` | `int64` | จำนวนผู้โดยสาร (คนขับกรอก) |
| `trip_distance` | `double` | ระยะทาง (ไมล์) |
| `RatecodeID` | `int64` | รหัสอัตราค่าโดยสาร |
| `store_and_fwd_flag` | `string` | Y/N ข้อมูลถูกเก็บในรถก่อนส่งหรือไม่ |
| `PULocationID` | `int32` | โซนรับ (TLC Taxi Zone) |
| `DOLocationID` | `int32` | โซนส่ง (TLC Taxi Zone) |
| `payment_type` | `int64` | วิธีชำระเงิน |
| `fare_amount` | `double` | ค่าโดยสารตามมิเตอร์ |
| `extra` | `double` | ค่าธรรมเนียมเพิ่มเติม |
| `mta_tax` | `double` | ภาษี MTA |
| `tip_amount` | `double` | ทิป |
| `tolls_amount` | `double` | ค่าทางด่วน |
| `improvement_surcharge` | `double` | ค่าธรรมเนียม improvement |
| `total_amount` | `double` | ยอดรวม |
| `congestion_surcharge` | `double` | ค่าธรรมเนียมความแออัด |
| `Airport_fee` | `double` | ค่าธรรมเนียมสนามบิน |

### 3.2 Green (20 คอลัมน์)

| คอลัมน์ | ชนิด | คำอธิบาย |
|---|---|---|
| `VendorID` | `int32` | รหัสผู้ให้บริการระบบบันทึก trip |
| `lpep_pickup_datetime` | `timestamp[us]` | เวลารับผู้โดยสาร |
| `lpep_dropoff_datetime` | `timestamp[us]` | เวลาส่งผู้โดยสาร |
| `store_and_fwd_flag` | `string` | Y/N ข้อมูลถูกเก็บในรถก่อนส่งหรือไม่ |
| `RatecodeID` | `int64` | รหัสอัตราค่าโดยสาร |
| `PULocationID` | `int32` | โซนรับ (TLC Taxi Zone) |
| `DOLocationID` | `int32` | โซนส่ง (TLC Taxi Zone) |
| `passenger_count` | `int64` | จำนวนผู้โดยสาร (คนขับกรอก) |
| `trip_distance` | `double` | ระยะทาง (ไมล์) |
| `fare_amount` | `double` | ค่าโดยสารตามมิเตอร์ |
| `extra` | `double` | ค่าธรรมเนียมเพิ่มเติม |
| `mta_tax` | `double` | ภาษี MTA |
| `tip_amount` | `double` | ทิป |
| `tolls_amount` | `double` | ค่าทางด่วน |
| `ehail_fee` | `double` | ค่าธรรมเนียม e-hail |
| `improvement_surcharge` | `double` | ค่าธรรมเนียม improvement |
| `total_amount` | `double` | ยอดรวม |
| `payment_type` | `int64` | วิธีชำระเงิน |
| `trip_type` | `int64` | ประเภท trip (street-hail / dispatch) |
| `congestion_surcharge` | `double` | ค่าธรรมเนียมความแออัด |

### 3.3 FHV (7 คอลัมน์)

| คอลัมน์ | ชนิด | คำอธิบาย |
|---|---|---|
| `dispatching_base_num` | `string` | เลข base ของ TLC ที่ dispatch trip |
| `pickup_datetime` | `timestamp[us]` | เวลารับผู้โดยสาร |
| `dropOff_datetime` | `timestamp[us]` | เวลาส่งผู้โดยสาร |
| `PUlocationID` | `int64` | โซนรับ (TLC Taxi Zone) |
| `DOlocationID` | `int64` | โซนส่ง (TLC Taxi Zone) |
| `SR_Flag` | `int64` | แฟล็ก shared ride (1 หรือ Null) |
| `Affiliated_base_number` | `string` | เลข base ที่คนขับ/รถสังกัด |

### 3.4 FHVHV (24 คอลัมน์)

| คอลัมน์ | ชนิด | คำอธิบาย |
|---|---|---|
| `hvfhs_license_num` | `string` | ใบอนุญาตผู้ให้บริการ (HV0002 Juno, HV0003 Uber, HV0004 Via, HV0005 Lyft) |
| `dispatching_base_num` | `string` | เลข base ที่ dispatch trip |
| `originating_base_num` | `string` | เลข base ที่รับคำขอเดินทาง |
| `request_datetime` | `timestamp[us]` | เวลาที่ผู้โดยสารขอเดินทาง |
| `on_scene_datetime` | `timestamp[us]` | เวลาที่คนขับถึงจุดรับ |
| `pickup_datetime` | `timestamp[us]` | เวลารับผู้โดยสาร |
| `dropoff_datetime` | `timestamp[us]` | เวลาส่งผู้โดยสาร |
| `PULocationID` | `int32` | โซนรับ (TLC Taxi Zone) |
| `DOLocationID` | `int32` | โซนส่ง (TLC Taxi Zone) |
| `trip_miles` | `double` | ระยะทาง (ไมล์) |
| `trip_time` | `int64` | เวลาเดินทาง (วินาที) |
| `base_passenger_fare` | `double` | ค่าโดยสารพื้นฐาน |
| `tolls` | `double` | ค่าทางด่วน |
| `bcf` | `double` | Black Car Fund |
| `sales_tax` | `double` | ภาษีขาย |
| `congestion_surcharge` | `double` | ค่าธรรมเนียมความแออัด |
| `airport_fee` | `double` | ค่าธรรมเนียมสนามบิน |
| `tips` | `double` | ทิป |
| `driver_pay` | `double` | ค่าตอบแทนคนขับ |
| `shared_request_flag` | `string` | Y/N ผู้โดยสารขอแชร์ |
| `shared_match_flag` | `string` | Y/N จับคู่แชร์สำเร็จ |
| `access_a_ride_flag` | `string` | Y/N trip ของโครงการ Access-A-Ride |
| `wav_request_flag` | `string` | Y/N ขอรถ wheelchair accessible |
| `wav_match_flag` | `string` | Y/N ได้รถ wheelchair accessible |

## 4. Schema ของ Output (หลัง Standardize)

Output ถูกเขียนที่ `/{type}/{year}/{batch}` และขั้น Transform ทำเฉพาะ Standardize เท่านั้น
(ไม่เพิ่มคอลัมน์คำนวณ ไม่ตัดคอลัมน์อื่น และยังไม่เพิ่มคอลัมน์ metadata เช่น `batch_id`)

### 4.1 Yellow

เหมือน schema input ทุกคอลัมน์ (ตาราง 3.1) ไม่มีการเพิ่ม ลบ หรือแปลงชนิด

### 4.2 Green

เหมือน schema input ทุกคอลัมน์ (ตาราง 3.2) ไม่มีการเพิ่ม ลบ หรือแปลงชนิด

### 4.3 FHV

เหมือน schema input ทุกคอลัมน์ (ตาราง 3.3) ไม่มีการเพิ่ม ลบ หรือแปลงชนิด

### 4.4 FHVHV

คอลัมน์ Y/N ทั้ง 5 ตัวถูกแปลงเป็น `int8` (1 = Y, 0 = N) คอลัมน์อื่นเหมือน input

| คอลัมน์ | ชนิด Input | ชนิด Output | การเปลี่ยนแปลง |
|---|---|---|---|
| `shared_request_flag` | `string` | `int8` | Y → 1, N → 0 |
| `shared_match_flag` | `string` | `int8` | Y → 1, N → 0 |
| `access_a_ride_flag` | `string` | `int8` | Y → 1, N → 0 |
| `wav_request_flag` | `string` | `int8` | Y → 1, N → 0 |
| `wav_match_flag` | `string` | `int8` | Y → 1, N → 0 |
| `cbd_congestion_fee` | – | (ตัดทิ้ง) | ถ้ามีในไฟล์ต้นทางให้ drop พร้อมบันทึกหมายเหตุ (ไฟล์ 2024 ไม่มีคอลัมน์นี้) |
| คอลัมน์อื่นอีก 19 ตัว | – | เหมือน input | ไม่เปลี่ยน |
