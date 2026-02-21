#!/usr/bin/env bash
# ============================================================
# IoT接続テスト — cURLで手動確認
# Usage: bash scripts/test_iot_connection.sh [BASE_URL] [API_KEY] [DEVICE_ID]
# ============================================================
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
API_KEY="${2:-test-api-key-123}"
DEVICE_ID="${3:-Ace1}"

PASS=0
FAIL=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
print_header() {
  echo ""
  echo "============================================================"
  echo "  $1"
  echo "============================================================"
}

check_status() {
  local test_name="$1"
  local expected="$2"
  local actual="$3"

  if [ "$actual" -eq "$expected" ]; then
    echo "[PASS] $test_name (HTTP $actual)"
    PASS=$((PASS + 1))
  else
    echo "[FAIL] $test_name — expected $expected, got $actual"
    FAIL=$((FAIL + 1))
  fi
}

# ---------------------------------------------------------------------------
# Test 1: POST sensor data
# ---------------------------------------------------------------------------
print_header "Test 1: POST sensor data"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "${BASE_URL}/booking/api/iot/events/" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: ${API_KEY}" \
  -d "{
    \"device\": \"${DEVICE_ID}\",
    \"event_type\": \"sensor_reading\",
    \"payload\": {
      \"mq9\": 123.4,
      \"light\": 456.7,
      \"sound\": 78.9,
      \"pir\": true
    }
  }")

check_status "POST /booking/api/iot/events/" 201 "$HTTP_CODE"

# Show response body for debugging
echo "Response body:"
curl -s \
  -X POST "${BASE_URL}/booking/api/iot/events/" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: ${API_KEY}" \
  -d "{
    \"device\": \"${DEVICE_ID}\",
    \"event_type\": \"sensor_reading\",
    \"payload\": {
      \"mq9\": 100.0,
      \"light\": 200.0,
      \"sound\": 30.0,
      \"pir\": false
    }
  }" | python3 -m json.tool 2>/dev/null || echo "(could not parse JSON)"

# ---------------------------------------------------------------------------
# Test 2: GET config
# ---------------------------------------------------------------------------
print_header "Test 2: GET config"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X GET "${BASE_URL}/booking/api/iot/config/?device=${DEVICE_ID}" \
  -H "X-API-KEY: ${API_KEY}")

check_status "GET /booking/api/iot/config/?device=${DEVICE_ID}" 200 "$HTTP_CODE"

echo "Config response:"
curl -s \
  -X GET "${BASE_URL}/booking/api/iot/config/?device=${DEVICE_ID}" \
  -H "X-API-KEY: ${API_KEY}" | python3 -m json.tool 2>/dev/null || echo "(could not parse JSON)"

# ---------------------------------------------------------------------------
# Test 3: Sequential POSTs (time-series data)
# ---------------------------------------------------------------------------
print_header "Test 3: Sequential POSTs (3x, 10s interval)"

for i in 1 2 3; do
  MQ9_VAL=$(echo "100 + $i * 50" | bc)
  LIGHT_VAL=$(echo "200 + $i * 30" | bc)
  SOUND_VAL=$(echo "40 + $i * 10" | bc)
  PIR_VAL=$(( i % 2 == 1 ? 1 : 0 ))

  if [ "$PIR_VAL" -eq 1 ]; then
    PIR_JSON="true"
  else
    PIR_JSON="false"
  fi

  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${BASE_URL}/booking/api/iot/events/" \
    -H "Content-Type: application/json" \
    -H "X-API-KEY: ${API_KEY}" \
    -d "{
      \"device\": \"${DEVICE_ID}\",
      \"event_type\": \"sensor_reading\",
      \"payload\": {
        \"mq9\": ${MQ9_VAL},
        \"light\": ${LIGHT_VAL},
        \"sound\": ${SOUND_VAL},
        \"pir\": ${PIR_JSON}
      }
    }")

  check_status "POST #${i} (mq9=${MQ9_VAL}, light=${LIGHT_VAL}, sound=${SOUND_VAL}, pir=${PIR_JSON})" 201 "$HTTP_CODE"

  if [ "$i" -lt 3 ]; then
    echo "  Waiting 10 seconds..."
    sleep 10
  fi
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print_header "Summary"
TOTAL=$((PASS + FAIL))
echo "Total: ${TOTAL}  |  PASS: ${PASS}  |  FAIL: ${FAIL}"

if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo "Some tests FAILED. Check the Django server logs for details."
  exit 1
else
  echo ""
  echo "All tests PASSED."
  exit 0
fi
