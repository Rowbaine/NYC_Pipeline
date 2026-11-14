#!/usr/bin/env bash
# deploy.sh - สร้าง S3 bucket พร้อมโฟลเดอร์ incoming/ raw/ trusted/ curated/ quarantine/
#             และ (ด้วย --setup) สร้าง/อัปเดต Lambda 6 ตัวจากโฟลเดอร์ infra/lambda_function/
#
# วิธีใช้:  bash infra/deploy.sh [--setup] [BUCKET_NAME] [REGION]
#   หรือกำหนดด้วยตัวแปร:  BUCKET_NAME=... AWS_REGION=... bash infra/deploy.sh
# ค่าเริ่มต้น: BUCKET_NAME = nyc-taxi-pipeline-<AWS account id>
#             REGION = ค่าที่ตั้งไว้ใน aws configure (ถ้าไม่มี ใช้ ap-southeast-1)
# --setup  : หลังสร้าง S3 แล้ว แพ็ก zip ต่อ function (+ common/ + data_contract/) แล้วสร้างหรืออัปเดต Lambda
#   ตัวแปรของ --setup (ไม่บังคับ):
#     ROLE_ARN  (ค่าเริ่มต้น arn:aws:iam::<account id>:role/LabRole)
#     LAYER_ARN (ค่าเริ่มต้น AWS SDK for pandas Python312 version 32; เปลี่ยนเลข version ด้วย LAYER_VERSION)
#     LAMBDA_PREFIX (nyc-taxi) LAMBDA_RUNTIME (python3.12) LAMBDA_TIMEOUT (900)
#     LAMBDA_MEMORY (3008) LAMBDA_EPHEMERAL (5120)
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

SETUP=0
ARGS=()
for a in "$@"; do
  if [[ "$a" == "--setup" ]]; then SETUP=1; else ARGS+=("$a"); fi
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

[[ $SETUP -eq 1 ]] || exit 0

# ---------------------------------------------------------------- --setup: Lambda
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

PY="$(command -v python3 || command -v python || true)"
[[ -n "$PY" ]] || die "ไม่พบ python3/python (ใช้สร้างไฟล์ zip)"
[[ -d "$LAMBDA_DIR/common" && -d "$CONTRACT_DIR" ]] || die "ไม่พบโฟลเดอร์ lambda_function/common หรือ script/data_contract"
for f in "${FUNCTIONS[@]}"; do
  [[ -f "$LAMBDA_DIR/$f/lambda_function.py" ]] || die "ไม่พบ $LAMBDA_DIR/$f/lambda_function.py"
done

# layer ที่มี pyarrow: AWS SDK for pandas (managed layer ของ AWS บัญชี 336392948345)
# ค่าเริ่มต้น = AWSSDKPandas-Python312 version 32 (us-east-1) เปลี่ยนได้ด้วย LAYER_VERSION หรือ LAYER_ARN
LAYER_VERSION="${LAYER_VERSION:-32}"
LAYER_ARN="${LAYER_ARN:-arn:aws:lambda:${REGION}:336392948345:layer:AWSSDKPandas-Python312:${LAYER_VERSION}}"

log ""
log "== Lambda | role: $ROLE_ARN"
log "           layer: $LAYER_ARN"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

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
