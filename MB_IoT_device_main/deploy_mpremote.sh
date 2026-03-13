#!/usr/bin/env bash
set -e
DEVICE=${1:-/dev/cu.usbmodem11101}
BASE="/Users/adon/MB_IoT"
echo "Deploying files from $BASE to $DEVICE ..."
# create directories on device
find "$BASE" -type d | while read d; do
  rel="${d#$BASE/}"
  if [ -z "$rel" ]; then rel="/"; fi
  mpremote connect "$DEVICE" fs mkdir "$rel" || true
done
# upload files
find "$BASE" -type f | while read f; do
  rel="${f#$BASE/}"
  echo "Uploading $rel ..."
  mpremote connect "$DEVICE" fs put "$f" "$rel"
done
echo "Deploy complete."
