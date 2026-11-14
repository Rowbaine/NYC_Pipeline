#!/usr/bin/env bash
# deploy.sh - สร้าง S3 bucket พร้อมโฟลเดอร์ incoming/ raw/ trusted/ curated/ quarantine/
#
# วิธีใช้:  bash infra/deploy.sh [BUCKET_NAME] [REGION]
#   หรือกำหนดด้วยตัวแปร:  BUCKET_NAME=... AWS_REGION=... bash infra/deploy.sh
# ค่าเริ่มต้น: BUCKET_NAME = nyc-taxi-pipeline-<AWS account id>
#             REGION = ค่าที่ตั้งไว้ใน aws configure (ถ้าไม่มี ใช้ ap-southeast-1)
# รันซ้ำได้ (idempotent): ถ้า bucket หรือโฟลเดอร์มีอยู่แล้วจะข้าม
set -euo pipefail

PREFIXES=(incoming raw trusted curated quarantine)
DEFAULT_REGION="ap-southeast-1"

log() { printf '%s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

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
