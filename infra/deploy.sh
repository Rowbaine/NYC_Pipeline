#!/usr/bin/env bash
# deploy.sh - สร้าง S3 bucket พร้อมโฟลเดอร์ incoming/ raw/ trusted/ curated/ quarantine/
#             และสร้าง/อัปเดต Lambda 6 ตัวจากโฟลเดอร์ infra/lambda_function/
#
# วิธีใช้:  bash infra/deploy.sh [BUCKET_NAME] [REGION]
#           bash infra/deploy.sh --run [BUCKET_NAME] [REGION]   # สั่งรัน pipeline (ไม่สร้าง S3/Lambda)
#   หรือกำหนดด้วยตัวแปร:  BUCKET_NAME=... AWS_REGION=... bash infra/deploy.sh
# ค่าเริ่มต้น: BUCKET_NAME = nyc-taxi-pipeline-<AWS account id>
#             REGION = ค่าที่ตั้งไว้ใน aws configure (ถ้าไม่มี ใช้ ap-southeast-1)
# หลังสร้าง S3 แล้ว แพ็ก zip ต่อ function (+ common/ + data_contract/) แล้วสร้างหรืออัปเดต Lambda
#   ตัวแปรของขั้น Lambda (ไม่บังคับ):
#     ROLE_ARN  (ค่าเริ่มต้น arn:aws:iam::<account id>:role/LabRole)
#     LAYER_ARN (ไม่ใส่ = ใช้/สร้าง layer <prefix>-pyarrow ที่มี zstd เอง; REBUILD_LAYER=1 สร้างใหม่; PYARROW_VERSION)
#     LAMBDA_PREFIX (nyc-taxi) LAMBDA_RUNTIME (python3.12) LAMBDA_TIMEOUT (900)
#     LAMBDA_MEMORY (3008) LAMBDA_EPHEMERAL (5120)
# --run    : อ่านไฟล์ .parquet ทั้งหมดใน incoming/ แล้วรันทีละไฟล์ batch -> ingest -> validate -> transform -> [quarantine] -> verify (-> curated)
#            quarantine รันเฉพาะเมื่อมีแถวไม่ผ่าน; verify ผ่านแล้วจึงคัดลอกไป curated/
#            ไฟล์ที่ล้มเหลวจะถูกข้าม รันไฟล์อื่นต่อ แล้วสรุปผลท้ายสุด (exit 1 ถ้ามีไฟล์ล้มเหลว) ต้อง deploy Lambda ไว้ก่อน
# รันซ้ำได้ (idempotent): ถ้า bucket, โฟลเดอร์ หรือ Lambda มีอยู่แล้วจะข้าม/อัปเดตแทนสร้างใหม่
set -euo pipefail

PREFIXES=(incoming raw trusted curated quarantine)
DEFAULT_REGION="us-east-1"

log() { printf '%s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'
  exit 0
fi

RUN=0
ARGS=()
for a in "$@"; do
  case "$a" in
    --setup) ;;            # ยังรับได้ (เหมือนเดิม) แต่ไม่จำเป็นแล้ว
    --run) RUN=1 ;;
    *) ARGS+=("$a") ;;
  esac
done
set -- ${ARGS[@]+"${ARGS[@]}"}

command -v aws >/dev/null 2>&1 || die "ไม่พบ AWS CLI (aws) กรุณาติดตั้งก่อน"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
  || die "เรียก AWS ไม่ได้ ตรวจ credentials ด้วย aws configure"

BUCKET="${1:-${BUCKET_NAME:-nyc-taxi-pipeline-${ACCOUNT_ID}}}"
REGION="${2:-${AWS_REGION:-${AWS_DEFAULT_REGION:-$(aws configure get region 2>/dev/null || true)}}}"
REGION="${REGION:-$DEFAULT_REGION}"

[[ "$BUCKET" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]] \
  || die "ชื่อ bucket ไม่ถูกต้อง '$BUCKET' (ใช้ a-z 0-9 . - ยาว 3-63 ตัว ขึ้นต้นและลงท้ายด้วยตัวอักษรหรือตัวเลข)"

log "Account: $ACCOUNT_ID | Bucket: $BUCKET | Region: $REGION"

# เลือก python ที่รันได้จริง (บน Windows python3 อาจเป็นตัวหลอกของ Microsoft Store ที่รันไม่ได้)
PY=""
for cand in python3 python py; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import zipfile" >/dev/null 2>&1; then PY="$cand"; break; fi
done
[[ -n "$PY" ]] || die "ไม่พบ python ที่ใช้งานได้ (ใช้สร้างไฟล์ zip) ลองติดตั้ง Python หรือปิด App execution aliases ของ python ใน Windows Settings"

# ---------------------------------------------------------------- --run: สั่งรัน pipeline
if [[ $RUN -eq 1 ]]; then
  LAMBDA_PREFIX="${LAMBDA_PREFIX:-nyc-taxi}"
  CHAIN=(batch_function ingest_function validate_function transform_function quarantine_function verify_batch_function)

  keys="$(aws s3api list-objects-v2 --bucket "$BUCKET" --prefix "incoming/" --region "$REGION" \
    --query "Contents[?ends_with(Key, '.parquet')].Key" --output text 2>/dev/null || true)"
  [[ -n "$keys" && "$keys" != "None" ]] || die "ไม่พบไฟล์ .parquet ใน s3://$BUCKET/incoming/ (อัปโหลดไฟล์ก่อน)"
  mapfile -t KEYS < <(printf '%s\n' $keys | tr -d '\r' | sort)
  log "พบ ${#KEYS[@]} ไฟล์ใน incoming/ | รันทีละไฟล์: ${CHAIN[*]}"

  WORK="$(mktemp -d)"
  trap 'rm -rf "$WORK"' EXIT
  cd "$WORK"

  json_get() { PYTHONUTF8=1 PYTHONIOENCODING=utf-8 "$PY" -c 'import json,sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    v = d.get(sys.argv[2], "") if isinstance(d, dict) else ""
except Exception:
    v = ""
print(v)' "$1" "$2" | tr -d '\r'; }

  # รัน Lambda ทีละตัว: $1 = ชื่อ function, $2 = ไฟล์ payload, $3 = ไฟล์ผลลัพธ์ -> คืน 0 เมื่อสำเร็จ (ข้อผิดพลาดเก็บใน ERR_MSG)
  invoke() {
    local fe
    if ! fe="$(aws lambda invoke --function-name "$1" --region "$REGION" --cli-read-timeout 0 \
        --payload "fileb://$2" --query FunctionError --output text "$3" 2>&1)"; then
      ERR_MSG="เรียก $1 ไม่ได้: $fe"; return 1
    fi
    if [[ "$fe" != "None" && -n "$fe" ]]; then
      ERR_MSG="$(json_get "$3" errorType): $(json_get "$3" errorMessage)"; return 1
    fi
    return 0
  }

  OK=0; SKIP=0; FAIL=0; SUMMARY=()
  i=0
  for key in "${KEYS[@]}"; do
    i=$((i + 1))
    log ""
    log "[$i/${#KEYS[@]}] $key"
    printf '{"key": "%s", "bucket": "%s"}' "$key" "$BUCKET" > in.json
    failed=""; result=""
    for f in "${CHAIN[@]}"; do
      fname="${LAMBDA_PREFIX}-${f//_/-}"
      if [[ "$f" == "quarantine_function" && "$(json_get in.json rows_invalid)" == "0" ]]; then
        log "    ข้าม: $f (ไม่มีแถวที่ไม่ผ่าน)"; continue
      fi
      if ! invoke "$fname" in.json out.json; then
        failed="$f"; break
      fi
      log "    ผ่าน: $f"
      cp out.json in.json
      if [[ "$(json_get out.json duplicate)" == "True" ]]; then result="DUPLICATE"; break; fi
    done
    if [[ -n "$failed" ]]; then
      FAIL=$((FAIL + 1)); SUMMARY+=("FAILED     $key  [$failed] $ERR_MSG"); log "    ล้มเหลวที่ $failed: $ERR_MSG"
    elif [[ "$result" == "DUPLICATE" ]]; then
      SKIP=$((SKIP + 1)); SUMMARY+=("SKIPPED    $key  (batch นี้ verify แล้ว)")
    else
      OK=$((OK + 1))
      SUMMARY+=("VERIFIED   $key  valid=$(json_get out.json rows_valid) quarantine=$(json_get out.json rows_invalid) curated=$(json_get out.json rows_curated)")
    fi
  done

  log ""
  log "== สรุป =="
  printf '%s\n' "${SUMMARY[@]}"
  log "สำเร็จ $OK | ข้าม $SKIP | ล้มเหลว $FAIL | รวม ${#KEYS[@]}"
  [[ $FAIL -eq 0 ]] || exit 1
  exit 0
fi

# 1) สร้าง bucket (ข้ามถ้ามีอยู่แล้วและเข้าถึงได้)
set +e
HEAD_OUT="$(aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" 2>&1)"
HEAD_RC=$?
set -e

if [[ $HEAD_RC -eq 0 ]]; then
  log "bucket มีอยู่แล้ว ข้ามขั้นสร้าง bucket"
elif [[ "$HEAD_OUT" == *"404"* || "$HEAD_OUT" == *"Not Found"* ]]; then
  log "กำลังสร้าง bucket..."
  if [[ "$REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
      --create-bucket-configuration "LocationConstraint=$REGION" >/dev/null
  fi
  aws s3api wait bucket-exists --bucket "$BUCKET" --region "$REGION"
  log "สร้าง bucket แล้ว"
else
  die "เข้าถึง bucket '$BUCKET' ไม่ได้ (ชื่ออาจถูกใช้โดยบัญชีอื่น, ไม่มีสิทธิ์ หรือ region ไม่ตรง): $HEAD_OUT"
fi

# 2) สร้างโฟลเดอร์ (object ว่างที่ key ลงท้ายด้วย /)
for p in "${PREFIXES[@]}"; do
  key="${p}/"
  if aws s3api head-object --bucket "$BUCKET" --key "$key" --region "$REGION" >/dev/null 2>&1; then
    log "  มีอยู่แล้ว: s3://$BUCKET/$key"
  else
    aws s3api put-object --bucket "$BUCKET" --key "$key" --region "$REGION" >/dev/null
    log "  สร้างแล้ว:  s3://$BUCKET/$key"
  fi
done

# 3) ตรวจว่าครบทุกโฟลเดอร์
for p in "${PREFIXES[@]}"; do
  aws s3api head-object --bucket "$BUCKET" --key "${p}/" --region "$REGION" >/dev/null 2>&1 \
    || die "ตรวจไม่พบ s3://$BUCKET/${p}/ หลังสร้าง"
done

log "เสร็จ: s3://$BUCKET/ มีโฟลเดอร์ ${PREFIXES[*]}"

# ---------------------------------------------------------------- Lambda
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAMBDA_DIR="$SCRIPT_DIR/lambda_function"
CONTRACT_DIR="$SCRIPT_DIR/../script/data_contract"
FUNCTIONS=(batch_function ingest_function validate_function transform_function quarantine_function verify_batch_function)
LAMBDA_PREFIX="${LAMBDA_PREFIX:-nyc-taxi}"
LAMBDA_RUNTIME="${LAMBDA_RUNTIME:-python3.12}"
LAMBDA_TIMEOUT="${LAMBDA_TIMEOUT:-900}"
LAMBDA_MEMORY="${LAMBDA_MEMORY:-3008}"
LAMBDA_EPHEMERAL="${LAMBDA_EPHEMERAL:-5120}"
ROLE_ARN="${ROLE_ARN:-arn:aws:iam::${ACCOUNT_ID}:role/LabRole}"

# จากตรงนี้ ถ้าคำสั่งไหนล้มเหลวแล้วสคริปต์หยุด ให้บอกบรรทัดที่พัง (กันกรณีหยุดเงียบๆ)
trap 'printf "ERROR: คำสั่งล้มเหลวที่บรรทัด %s (exit %s)\n" "$LINENO" "$?" >&2' ERR
[[ -d "$LAMBDA_DIR/common" && -d "$CONTRACT_DIR" ]] || die "ไม่พบโฟลเดอร์ lambda_function/common หรือ script/data_contract"
for f in "${FUNCTIONS[@]}"; do
  [[ -f "$LAMBDA_DIR/$f/lambda_function.py" ]] || die "ไม่พบ $LAMBDA_DIR/$f/lambda_function.py"
done

log ""
log "== Lambda | role: $ROLE_ARN"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# layer ที่มี pyarrow (รองรับ zstd ซึ่งไฟล์ TLC ใช้ แต่ layer สำเร็จรูปของ AWS ไม่รองรับ)
# ใช้ LAYER_ARN ที่กำหนดเอง หรือ layer ชื่อ <prefix>-pyarrow ที่มีอยู่แล้ว หรือสร้างใหม่จาก pip (REBUILD_LAYER=1 บังคับสร้างใหม่)
LAYER_NAME="${LAMBDA_PREFIX}-pyarrow"
PYARROW_VERSION="${PYARROW_VERSION:-25.0.1}"
if [[ -z "${LAYER_ARN:-}" && "${REBUILD_LAYER:-0}" != "1" ]]; then
  LAYER_ARN="$(aws lambda list-layer-versions --layer-name "$LAYER_NAME" --region "$REGION" \
    --query 'LayerVersions[0].LayerVersionArn' --output text 2>/dev/null || true)"
  [[ "$LAYER_ARN" != "None" ]] || LAYER_ARN=""
fi
if [[ -z "${LAYER_ARN:-}" || "${REBUILD_LAYER:-0}" == "1" ]]; then
  log "สร้าง layer $LAYER_NAME (pyarrow==$PYARROW_VERSION สำหรับ ${LAMBDA_RUNTIME}) ใช้เวลาสักครู่..."
  PYVER="${LAMBDA_RUNTIME#python}"
  "$PY" -m pip install --quiet --disable-pip-version-check --target "$WORK/layer/python" \
    --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 \
    --python-version "$PYVER" --implementation cp --only-binary=:all: "pyarrow==$PYARROW_VERSION" \
    || die "ติดตั้ง pyarrow==$PYARROW_VERSION สำหรับ layer ไม่สำเร็จ (ตรวจอินเทอร์เน็ต/เวอร์ชัน)"
  (cd "$WORK" && "$PY" - layer pyarrow-layer.zip <<'PYEOF'
import os, sys, zipfile
src, out = sys.argv[1:3]
skip_dirs = {"__pycache__", "include", "tests"}
skip_ext = (".pxd", ".pyx", ".pxi", ".h", ".hpp")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in sorted(files):
            if not f.endswith(skip_ext):
                p = os.path.join(root, f)
                z.write(p, os.path.relpath(p, src).replace(os.sep, "/"))
PYEOF
  )
  LAYER_KEY="_layers/${LAYER_NAME}.zip"
  (cd "$WORK" && aws s3 cp pyarrow-layer.zip "s3://$BUCKET/$LAYER_KEY" --region "$REGION" >/dev/null) \
    || die "อัปโหลด layer ไป s3://$BUCKET/$LAYER_KEY ไม่สำเร็จ"
  LAYER_ARN="$(aws lambda publish-layer-version --layer-name "$LAYER_NAME" --region "$REGION" \
    --description "pyarrow==$PYARROW_VERSION (with zstd)" --compatible-runtimes "$LAMBDA_RUNTIME" \
    --content "S3Bucket=$BUCKET,S3Key=$LAYER_KEY" --query LayerVersionArn --output text)" \
    || die "สร้าง layer ไม่สำเร็จ"
  log "  สร้าง layer แล้ว: $LAYER_ARN"
fi
log "           layer: $LAYER_ARN"

# zip: lambda_function.py อยู่ราก + common/ + data_contract/ (เฉพาะ .py)
make_zip() {  # $1 = ชื่อโฟลเดอร์ function, $2 = ไฟล์ zip ปลายทาง
  (cd "$WORK" && "$PY" - "$LAMBDA_DIR/$1" "$LAMBDA_DIR/common" "$CONTRACT_DIR" "$2" <<'PYEOF'
import os, sys, zipfile
fn_dir, common_dir, contract_dir, out = sys.argv[1:5]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(os.path.join(fn_dir, "lambda_function.py"), "lambda_function.py")
    for top, name in ((common_dir, "common"), (contract_dir, "data_contract")):
        for root, dirs, files in os.walk(top):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in sorted(files):
                if f.endswith(".py"):
                    path = os.path.join(root, f)
                    z.write(path, name + "/" + os.path.relpath(path, top).replace(os.sep, "/"))
PYEOF
  )
}

ENV_VARS="Variables={BUCKET_NAME=${BUCKET},BATCH_ROWS=500000}"
for f in "${FUNCTIONS[@]}"; do
  name="${LAMBDA_PREFIX}-${f//_/-}"
  zipname="${f}.zip"
  make_zip "$f" "$zipname"
  if aws lambda get-function --function-name "$name" --region "$REGION" >/dev/null 2>&1; then
    (cd "$WORK" && aws lambda update-function-code --function-name "$name" --region "$REGION" \
      --zip-file "fileb://$zipname" >/dev/null)
    aws lambda wait function-updated --function-name "$name" --region "$REGION"
    aws lambda update-function-configuration --function-name "$name" --region "$REGION" \
      --runtime "$LAMBDA_RUNTIME" --role "$ROLE_ARN" --handler lambda_function.lambda_handler \
      --timeout "$LAMBDA_TIMEOUT" --memory-size "$LAMBDA_MEMORY" \
      --ephemeral-storage "Size=$LAMBDA_EPHEMERAL" --layers "$LAYER_ARN" \
      --environment "$ENV_VARS" >/dev/null
    aws lambda wait function-updated --function-name "$name" --region "$REGION"
    log "  อัปเดตแล้ว:  $name"
  else
    (cd "$WORK" && aws lambda create-function --function-name "$name" --region "$REGION" \
      --runtime "$LAMBDA_RUNTIME" --role "$ROLE_ARN" --handler lambda_function.lambda_handler \
      --zip-file "fileb://$zipname" --timeout "$LAMBDA_TIMEOUT" --memory-size "$LAMBDA_MEMORY" \
      --ephemeral-storage "Size=$LAMBDA_EPHEMERAL" --layers "$LAYER_ARN" \
      --environment "$ENV_VARS" >/dev/null)
    aws lambda wait function-active-v2 --function-name "$name" --region "$REGION" 2>/dev/null \
      || aws lambda wait function-active --function-name "$name" --region "$REGION"
    log "  สร้างแล้ว:   $name"
  fi
done

# ตรวจว่า Lambda ทุกตัวพร้อมใช้งาน
for f in "${FUNCTIONS[@]}"; do
  name="${LAMBDA_PREFIX}-${f//_/-}"
  state="$(aws lambda get-function-configuration --function-name "$name" --region "$REGION" \
    --query 'State' --output text 2>/dev/null || true)"
  [[ "$state" == "Active" ]] || die "Lambda $name สถานะ '$state' (ต้องเป็น Active)"
done
log "เสร็จ: Lambda ${#FUNCTIONS[@]} ตัว (${LAMBDA_PREFIX}-*) พร้อมใช้งาน | BUCKET_NAME=$BUCKET"
