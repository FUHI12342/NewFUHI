#!/bin/bash
# ===== NewFUHI Backup Script =====
# 目的: media + DB を S3 にバックアップ
# DB_TYPE: sqlite (default) | postgres
# 確認コマンド例:
#   ./scripts/backup_to_s3.sh; echo $?
#   /usr/local/bin/aws s3 ls s3://mee-newfuhi-backups/db/ | tail
#   /usr/local/bin/aws s3 ls s3://mee-newfuhi-backups/media/ | head
# cron 例（このスクリプトが backup.log に書くので、cron 側で >> backup.log は付けない）:
#   0 2 * * * /bin/bash -lc '/Users/adon/NewFUHI/scripts/backup_to_s3.sh'
set -euo pipefail

# ===== Load env (LINE_NOTIFY_TOKEN etc.) =====
# Priority: .env.local -> .env.production -> .env
load_env_file() {
  local f="$1"
  if [ -f "$f" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$f"
    set +a
  fi
}

# ===== Config =====
PROJECT_DIR="/Users/adon/NewFUHI"
load_env_file "${PROJECT_DIR}/.env.local"
load_env_file "${PROJECT_DIR}/.env.production"
load_env_file "${PROJECT_DIR}/.env"

MEDIA_DIR="${PROJECT_DIR}/media"
DB_FILE="${PROJECT_DIR}/db.sqlite3"
BACKUP_DIR="${PROJECT_DIR}/backups"
LOG_FILE="${PROJECT_DIR}/backup.log"
LOCK_DIR="${PROJECT_DIR}/backup.lock"

AWS="/usr/local/bin/aws"
S3_BUCKET="s3://mee-newfuhi-backups"
S3_MEDIA_PATH="${S3_BUCKET}/media"
S3_DB_PATH="${S3_BUCKET}/db"

DB_TYPE="${DB_TYPE:-sqlite}"  # default: sqlite
KEEP_LOCAL_DB_BACKUPS=30
KEEP_S3_DB_BACKUPS="${KEEP_S3_DB_BACKUPS:-90}"  # S3 retention
TS="$(date +%Y%m%d_%H%M%S)"
DB_BAK="${BACKUP_DIR}/db.${DB_TYPE}.bak_${TS}"

ERROR_NOTIFIED=0  # Global flag to prevent duplicate notifications

# ===== Functions =====
log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "${LOG_FILE}"
}

notify_line() {
  local message="$1"
  if [ -n "${LINE_NOTIFY_TOKEN:-}" ]; then
    local response
    response=$(curl -s -w "HTTPSTATUS:%{http_code};" -X POST https://notify-api.line.me/api/notify \
      -H "Authorization: Bearer ${LINE_NOTIFY_TOKEN}" \
      -F "message=${message}" 2>/dev/null)
    local http_code
    http_code=$(echo "${response}" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    local body
    body=$(echo "${response}" | sed -e 's/HTTPSTATUS:.*//g')
    if [ "${http_code}" = "200" ]; then
      log "[OK] LINE notify sent (http=${http_code})"
    else
      log "[WARN] LINE notify failed (http=${http_code}, body=${body})"
    fi
  fi
}

notify_failure() {
  local message="$1"
  ERROR_NOTIFIED=1
  notify_line "[FAIL] ${message}"
}

notify_success() {
  local message="$1"
  notify_line "[OK] ${message}"
}

notify_heartbeat_once_per_day() {
  # Success heartbeat: send at most once per day
  local state_dir="${BACKUP_DIR}/.state"
  mkdir -p "${state_dir}"
  local today_file="${state_dir}/heartbeat_$(date +%Y%m%d).sent"
  if [ ! -f "${today_file}" ]; then
    log "[INFO] sending heartbeat"
    notify_success "Backup heartbeat OK (${TS})"
    : > "${today_file}"
  fi
}

on_exit() {
  local rc=$?
  if [ $rc -ne 0 ] && [ $ERROR_NOTIFIED -eq 0 ]; then
    log "[ERROR] backup exiting with rc=${rc} (EXIT trap)"
    notify_failure "Backup failed (exit=${rc}) on $(hostname) at ${TS}. See ${LOG_FILE}"
  fi
  # Always clean up lock
  rm -rf "${LOCK_DIR}" 2>/dev/null || true
}

backup_db_sqlite() {
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "${DB_FILE}" ".backup '${DB_BAK}'"
    log "[OK] db backup created (sqlite3): ${DB_BAK}"
  else
    cp -p "${DB_FILE}" "${DB_BAK}"
    log "[OK] db backup created (cp): ${DB_BAK}"
  fi
}

backup_db_postgres() {
  # env: PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD
  if [ -z "${PGHOST:-}" ] || [ -z "${PGDATABASE:-}" ] || [ -z "${PGUSER:-}" ]; then
    log "[ERROR] postgres env not set: PGHOST, PGDATABASE, PGUSER required"
    exit 5
  fi
  pg_dump | gzip > "${DB_BAK}.gz"
  log "[OK] db backup created (postgres): ${DB_BAK}.gz"
}

upload_db_and_pointers() {
  local db_file="$1"
  local manifest_file="${BACKUP_DIR}/manifest_latest.json"
  local latest_file="${BACKUP_DIR}/latest.txt"

  # Upload DB
  "${AWS}" s3 cp "${db_file}" "${S3_DB_PATH}/" >> "${LOG_FILE}" 2>&1
  log "[OK] db backup uploaded to S3: ${db_file}"

  # Create latest.txt
  echo "$(basename "${db_file}")" > "${latest_file}"
  "${AWS}" s3 cp "${latest_file}" "${S3_DB_PATH}/" >> "${LOG_FILE}" 2>&1

  # Create manifest
  cat > "${manifest_file}" <<EOF
{
  "project": "NewFUHI",
  "version": "1.0",
  "db_type": "${DB_TYPE}",
  "timestamp": "${TS}",
  "db_file": "$(basename "${db_file}")",
  "s3_db_key": "db/$(basename "${db_file}")",
  "latest_pointer": "db/latest.txt"
}
EOF
  "${AWS}" s3 cp "${manifest_file}" "${S3_DB_PATH}/" >> "${LOG_FILE}" 2>&1
  log "[OK] manifest uploaded: ${manifest_file}"
}

s3_retention_db() {
  # Prefer S3 Lifecycle rules in production. This is a best-effort cleanup.
  local days="${KEEP_S3_DB_BACKUPS}"
  if [ -z "${days}" ]; then
    return 0
  fi

  python3 - <<'PY' >> "${LOG_FILE}" 2>&1
import json, os, subprocess, sys
from datetime import datetime, timezone, timedelta

aws = os.environ.get("AWS", "/usr/local/bin/aws")
bucket = "mee-newfuhi-backups"
prefix = "db/"
days = int(os.environ.get("KEEP_S3_DB_BACKUPS", "90"))
cutoff = datetime.now(timezone.utc) - timedelta(days=days)

# list objects
cmd = [aws, "s3api", "list-objects-v2", "--bucket", bucket, "--prefix", prefix]
proc = subprocess.run(cmd, capture_output=True, text=True)
if proc.returncode != 0:
    print(proc.stdout)
    print(proc.stderr, file=sys.stderr)
    sys.exit(proc.returncode)

data = json.loads(proc.stdout or "{}")
contents = data.get("Contents") or []
old_keys = []
for obj in contents:
    key = obj.get("Key")
    lm = obj.get("LastModified")
    if not key or not lm:
        continue
    # LastModified is ISO8601 like 2025-12-20T05:36:22.000Z
    lm_dt = datetime.fromisoformat(lm.replace("Z", "+00:00"))
    if lm_dt <= cutoff:
        # avoid deleting pointers
        if key.endswith("latest.txt") or key.endswith("manifest_latest.json"):
            continue
        old_keys.append(key)

# delete old objects
for key in old_keys:
    rm = subprocess.run([aws, "s3", "rm", f"s3://{bucket}/{key}"]) 
    if rm.returncode != 0:
        sys.exit(rm.returncode)

print(f"[OK] S3 retention applied: keep {days} days, deleted {len(old_keys)} objects")
PY

  log "[OK] S3 retention attempted (keep ${KEEP_S3_DB_BACKUPS} days)"
}

sync_media() {
  "${AWS}" s3 sync "${MEDIA_DIR}" "${S3_MEDIA_PATH}" --delete >> "${LOG_FILE}" 2>&1
  log "[OK] media synced to S3"
}

local_retention_db() {
  ls -t "${BACKUP_DIR}"/db.*.bak_* 2>/dev/null | tail -n +$((KEEP_LOCAL_DB_BACKUPS+1)) | xargs -I{} rm -f "{}" || true
  log "[OK] local retention applied: keep ${KEEP_LOCAL_DB_BACKUPS}"
}

# ===== Main =====
# 二重起動防止（race-safe）
if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  log "[ERROR] backup already running (lock dir exists: ${LOCK_DIR})"
  exit 1
fi

# Traps
trap on_exit EXIT
trap 'rc=$?; log "[ERROR] backup failed (exit=${rc})"; tail -n 50 "${LOG_FILE}" | sed "s/^/[LOG] /" >> "${LOG_FILE}" 2>/dev/null || true; notify_failure "Backup failed (exit=${rc}) on $(hostname) at ${TS}. See ${LOG_FILE}"; exit ${rc}' ERR

mkdir -p "${BACKUP_DIR}"
log "==== backup start ${TS} ===="

# Sanity checks
if [ ! -x "${AWS}" ]; then
  log "[ERROR] aws not found at ${AWS}"
  exit 2
fi
if [ ! -d "${MEDIA_DIR}" ]; then
  log "[ERROR] media dir not found: ${MEDIA_DIR}"
  exit 4
fi

# DB backup
case "${DB_TYPE}" in
  sqlite)
    if [ ! -f "${DB_FILE}" ]; then
      log "[ERROR] sqlite db file not found: ${DB_FILE}"
      exit 3
    fi
    backup_db_sqlite
    upload_db_and_pointers "${DB_BAK}"
    ;;
  postgres)
    backup_db_postgres
    upload_db_and_pointers "${DB_BAK}.gz"
    ;;
  *)
    log "[ERROR] invalid DB_TYPE: ${DB_TYPE}"
    exit 6
    ;;
esac

# Media sync
sync_media

# Retention
s3_retention_db
local_retention_db

# Heartbeat
notify_heartbeat_once_per_day

log "==== backup done ${TS} (exit=0) ===="