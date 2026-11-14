"""เปรียบเทียบจำนวนเที่ยวของแท็กซี่ 4 ประเภท จากไฟล์ใน s3://<bucket>/curated/ ด้วย DuckDB

วิธีใช้:  python script/compare_taxi_types.py [BUCKET_NAME] [REGION]
  ค่าเริ่มต้น: BUCKET_NAME = nyc-taxi-pipeline-<AWS account id>, REGION = us-east-1
  credentials ใช้ชุดเดียวกับ aws configure (รวม session token ของ Learner Lab)
ต้องติดตั้ง:  pip install duckdb boto3

ผลลัพธ์ (แสดงบนจอ)
  1. ตารางรวมครึ่งปีแรก 2024: จำนวนเที่ยว, %, อันดับ
  2. ตารางรายเดือน: จำนวนเที่ยวต่อประเภทต่อเดือน
หมายเหตุ: curated/ มีเฉพาะ batch ที่ผ่าน VerifyBatch แล้ว ประเภทที่ยังไม่มีไฟล์จะแสดงเป็น 0 และแจ้งเตือน
"""
import os
import sys

import duckdb

TAXI_TYPES = ("yellow", "green", "fhv", "fhvhv")
YEAR = "2024"


def connect(region: str) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    try:
        import boto3

        creds = boto3.Session(region_name=region).get_credentials()
        if creds is None:
            raise RuntimeError("ไม่พบ AWS credentials (ตั้งด้วย aws configure)")
        c = creds.get_frozen_credentials()
        con.execute(
            "CREATE SECRET s3_creds (TYPE s3, KEY_ID ?, SECRET ?, SESSION_TOKEN ?, REGION ?)",
            [c.access_key, c.secret_key, c.token or "", region],
        )
    except ImportError:  # ไม่มี boto3: ให้ DuckDB อ่าน credentials จาก aws configure เอง
        con.execute("INSTALL aws; LOAD aws;")
        con.execute(f"CREATE SECRET s3_creds (TYPE s3, PROVIDER credential_chain, REGION '{region}')")
    return con


def default_bucket() -> str:
    import boto3

    account = boto3.client("sts").get_caller_identity()["Account"]
    return f"nyc-taxi-pipeline-{account}"


def files_of(con, bucket: str, taxi_type: str) -> list[str]:
    pattern = f"s3://{bucket}/curated/{taxi_type}/{YEAR}/*/*.parquet"
    return [r[0] for r in con.execute("SELECT file FROM glob(?)", [pattern]).fetchall()]


def main() -> int:
    bucket = sys.argv[1] if len(sys.argv) > 1 else (os.environ.get("BUCKET_NAME") or default_bucket())
    region = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("AWS_REGION", "us-east-1")
    con = connect(region)
    print(f"อ่านจาก s3://{bucket}/curated/ (region {region})")

    # รวมรายเดือนของทุกประเภทไว้ในตารางเดียว (อ่านไฟล์ของแต่ละประเภทแยกกัน เพราะคอลัมน์ไม่เหมือนกัน)
    con.execute("CREATE TABLE monthly (taxi_type VARCHAR, month VARCHAR, trips BIGINT)")
    missing = []
    for t in TAXI_TYPES:
        files = files_of(con, bucket, t)
        print(f"  {t:<7} {len(files)} ไฟล์")
        if not files:
            missing.append(t)
            continue
        con.execute(
            """INSERT INTO monthly
               SELECT ?, regexp_extract(filename, '_tripdata_([0-9]{4}-[0-9]{2})', 1), count(*)
               FROM read_parquet(?, filename = true)
               GROUP BY ALL""",
            [t, files],
        )

    print("\n== จำนวนเที่ยวรวม ครึ่งปีแรก 2024 ==")
    con.sql(
        """WITH types(taxi_type) AS (SELECT unnest(?::VARCHAR[])),
                total AS (SELECT t.taxi_type, coalesce(sum(m.trips), 0)::BIGINT AS trips
                          FROM types t LEFT JOIN monthly m USING (taxi_type) GROUP BY t.taxi_type)
           SELECT taxi_type, trips,
                  round(100.0 * trips / nullif(sum(trips) OVER (), 0), 2) AS pct,
                  rank() OVER (ORDER BY trips DESC) AS rank
           FROM total ORDER BY rank, taxi_type""",
        params=[list(TAXI_TYPES)],
    ).show()

    print("== จำนวนเที่ยวรายเดือน ==")
    con.sql(
        """PIVOT monthly ON taxi_type IN ('yellow', 'green', 'fhv', 'fhvhv')
           USING sum(trips) GROUP BY month ORDER BY month"""
    ).show()

    months = {r[0] for r in con.execute("SELECT DISTINCT taxi_type || month FROM monthly").fetchall()}
    if missing:
        print(f"คำเตือน: ยังไม่มีไฟล์ใน curated/ ของ {', '.join(missing)} (นับเป็น 0)")
    if len(months) < len(TAXI_TYPES) * 6:
        print(f"คำเตือน: มี {len(months)} จาก {len(TAXI_TYPES) * 6} batch (ประเภท x เดือน) ผลยังไม่ครบครึ่งปี")
    return 0


if __name__ == "__main__":
    sys.exit(main())
