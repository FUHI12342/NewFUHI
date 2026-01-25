#!/bin/bash
set -euo pipefail

ERROR_NOTIFIED=0

# ===== config =====
PROJECT_ROOT="/Users/adon/NewFUHI"
LOG_FILE="$PROJECT_ROOT/backup.log"
BACKUP_DIR="$PROJECT_ROOT/backups"
STATE_DIR="$BACKUP_DIR/.state"
LOCK_DIR="$BACKUP_DIR/backup.lock"
AWS_BIN="/usr/local/bin/aws"
S3_BUCKET="mee-newfuhi-backups"
S3_MEDIA_PREFIX="media"
S3_DB_PREFIX="db"
KEEP_LOCAL_DB_COUNT=${KEEP_LOCAL_DB_COUNT:-30}
KEEP_S3_DB_DAYS=${KEEP_S3_DB_DAYS:-90}

mkdir -p "$BACKUP_DIR" "$STATE_DIR"

# Load secrets from env files (NOT tracked by git)
# Priority: .env.local -> .env.production -> .env
for f in "$PROJECT_ROOT/.env.local" "$PROJECT_ROOT/.env.production" "$PROJECT_ROOT/.env"; do
  if [ -f "$f" ]; then
    # shellcheck disable=SC1090
    set -a
    . "$f"
    set +a
  fi
done

ts() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "$(ts) $*" >> "$LOG_FILE"; }

notify_line() {
  # usage: notify_line "message"
  local msg="$1"
  if [ -z "${LINE_NOTIFY_TOKEN:-}" ]; then
    log "[WARN] LINE_NOTIFY_TOKEN not set; skip LINE notify"
    return 0
  fi

  # Capture HTTP status and body for debugging (do not crash backup on notify failure)
  local tmp http_code rc
  tmp=$(/usr/bin/mktemp)
  http_code=$(/usr/bin/curl -sS -o "$tmp" -w "%{http_code}" \
    -X POST "https://notify-api.line.me/api/notify" \
    -H "Authorization: Bearer ${LINE_NOTIFY_TOKEN}" \
    --data-urlencode "message=${msg}" )
  rc=$?

  if [ "$rc" -ne 0 ] || [ "$http_code" != "200" ]; then
    log "[WARN] LINE notify failed rc=${rc} http=${http_code} body=$(tail -c 300 "$tmp" | tr '\n' ' ')"
    /bin/rm -f "$tmp" 2>/dev/null || true
    return 0
  fi

  log "[OK] LINE notify sent (http=${http_code})"
  /bin/rm -f "$tmp" 2>/dev/null || true
  return 0
}

notify_failure() {
  local rc="$1"
  log "[INFO] sending failure notify (rc=${rc})"
  notify_line "[FAIL] NewFUHI backup failed rc=${rc} host=$(hostname) at $(ts). See ${LOG_FILE}"
  ERROR_NOTIFIED=1
}

notify_heartbeat_once_per_day() {
  # Send success heartbeat once per day.
  local day
  day=$(date "+%Y%m%d")
  local mark="$STATE_DIR/heartbeat_${day}.sent"
  if [ ! -f "$mark" ]; then
    log "[INFO] sending heartbeat"
    notify_line "[OK] NewFUHI backup heartbeat ${day} host=$(hostname)"
    : > "$mark"
  fi
}

cleanup_lock() {
  if [ -d "$LOCK_DIR" ]; then
    rmdir "$LOCK_DIR" 2>/dev/null || true
  fi
}

on_error() {
  local rc=$?
  log "[ERROR] backup failed (rc=${rc})"
  notify_failure "$rc"
  cleanup_lock
  exit "$rc"
}

on_exit() {
  local rc=$?
  if [ "$rc" -ne 0 ] && [ "${ERROR_NOTIFIED}" -eq 0 ]; then
    log "[ERROR] backup exiting with rc=${rc} (EXIT trap)"
    notify_failure "$rc"
  fi
  cleanup_lock
}

trap on_error ERR
trap on_exit EXIT

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "[WARN] backup already running; lock exists: $LOCK_DIR"
  exit 0
fi

if [ ! -x "$AWS_BIN" ]; then
  log "[ERROR] aws not found at $AWS_BIN"
  false  # trigger ERR trap
fi

RUN_TS=$(date "+%Y%m%d_%H%M%S")
log "==== backup start ${RUN_TS} ===="

DB_BAK_FILE="$BACKUP_DIR/db.sqlite3.bak_${RUN_TS}"

if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$PROJECT_ROOT/db.sqlite3" ".backup '$DB_BAK_FILE'"
  log "[OK] db backup created (sqlite3): $DB_BAK_FILE"
else
  cp -p "$PROJECT_ROOT/db.sqlite3" "$DB_BAK_FILE"
  log "[OK] db backup created (cp): $DB_BAK_FILE"
fi

# Upload DB backup
"$AWS_BIN" s3 cp "$DB_BAK_FILE" "s3://$S3_BUCKET/$S3_DB_PREFIX/$(basename "$DB_BAK_FILE")"
log "[OK] db backup uploaded to S3: $DB_BAK_FILE"

# latest pointer (filename only)
LATEST_TXT="$BACKUP_DIR/latest.txt"
echo "$(basename "$DB_BAK_FILE")" > "$LATEST_TXT"
"$AWS_BIN" s3 cp "$LATEST_TXT" "s3://$S3_BUCKET/$S3_DB_PREFIX/latest.txt"

# manifest
MANIFEST="$BACKUP_DIR/manifest_latest.json"
export RUN_TS DB_BAK_FILE S3_BUCKET S3_DB_PREFIX
python3 - <<'PY'
import json, os, time
run_ts = os.environ.get('RUN_TS')
db_bak = os.environ.get('DB_BAK_FILE')
bucket = os.environ.get('S3_BUCKET')
prefix = os.environ.get('S3_DB_PREFIX')
obj = {
  "run_ts": run_ts,
  "db_type": "sqlite",
  "db_backup_file": os.path.basename(db_bak) if db_bak else None,
  "s3_db_key": f"{prefix}/{os.path.basename(db_bak)}" if (db_bak and prefix) else None,
  "s3_latest_key": f"{prefix}/latest.txt" if prefix else None,
  "created_unix": int(time.time()),
}
print(json.dumps(obj, ensure_ascii=False, indent=2))
PY
> "$MANIFEST"

"$AWS_BIN" s3 cp "$MANIFEST" "s3://$S3_BUCKET/$S3_DB_PREFIX/manifest_latest.json"
log "[OK] manifest uploaded: $MANIFEST"

# S3 retention (delete DB backups older than KEEP_S3_DB_DAYS)
python3 - <<'PY'
import datetime as dt
import json
import os
import subprocess

aws = os.environ['AWS_BIN']
bucket = os.environ['S3_BUCKET']
prefix = os.environ['S3_DB_PREFIX']
keep_days = int(os.environ.get('KEEP_S3_DB_DAYS', '90'))

# list objects
cmd = [aws, 's3api', 'list-objects-v2', '--bucket', bucket, '--prefix', f"{prefix}/"]
proc = subprocess.run(cmd, capture_output=True, text=True)
proc.check_returncode()
data = json.loads(proc.stdout or '{}')
contents = data.get('Contents', [])

now = dt.datetime.now(dt.timezone.utc)
cutoff = now - dt.timedelta(days=keep_days)

deleted = 0
for obj in contents:
    key = obj.get('Key')
    lm = obj.get('LastModified')
    if not key or not lm:
        continue
    # keep pointers
    if key.endswith('latest.txt') or key.endswith('manifest_latest.json'):
        continue
    # parse LastModified like 2025-12-20T06:05:04.000Z
    try:
        lm_dt = dt.datetime.fromisoformat(lm.replace('Z', '+00:00'))
    except Exception:
        continue
    if lm_dt < cutoff:
        del_cmd = [aws, 's3api', 'delete-object', '--bucket', bucket, '--key', key]
        subprocess.run(del_cmd, check=False)
        deleted += 1

print(f"deleted={deleted}")
PY
AWS_BIN="$AWS_BIN" S3_BUCKET="$S3_BUCKET" S3_DB_PREFIX="$S3_DB_PREFIX" KEEP_S3_DB_DAYS="$KEEP_S3_DB_DAYS" \
>> "$LOG_FILE" 2>&1
log "[OK] S3 retention applied: keep ${KEEP_S3_DB_DAYS} days"

"$AWS_BIN" s3 sync "$PROJECT_ROOT/media" "s3://$S3_BUCKET/$S3_MEDIA_PREFIX" --delete
log "[OK] media synced to S3"

ls -1t "$BACKUP_DIR"/db.sqlite3.bak_* 2>/dev/null | tail -n +$((KEEP_LOCAL_DB_COUNT+1)) | xargs -I{} rm -f "{}" || true
log "[OK] local retention applied: keep ${KEEP_LOCAL_DB_COUNT}"

log "==== backup done ${RUN_TS} (exit=0) ===="
notify_heartbeat_once_per_day
exit 0