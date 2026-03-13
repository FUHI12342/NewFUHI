#!/usr/bin/env bash
set -e
BASE="$(pwd)"
BACKUP="${BASE}/aws_test.py.bak"
if [ -f "${BASE}/aws_test.py" ]; then
  echo "Backing up existing aws_test.py to aws_test.py.bak"
  cp "${BASE}/aws_test.py" "${BACKUP}"
fi

echo "Creating split aws modules in ${BASE}"

# mqtt_client.py
cat > "${BASE}/mqtt_client.py" <<'PY'
# mqtt_client.py
import ssl
import socketpool
import wifi
import adafruit_minimqtt.adafruit_minimqtt as MQTT

# Configurable globals (set by aws_test wrapper)
AWS_ENDPOINT = None
CLIENT_ID = "pico_client"
CERT_FILE = None
KEY_FILE = None
ROOT_CA = None

def _create_mqtt_client(client_id, keepalive=60):
    try:
        pool = socketpool.SocketPool(wifi.radio)
        ctx = ssl.create_default_context()
        if not CERT_FILE or not KEY_FILE:
            raise RuntimeError("CERT_FILE/KEY_FILE not configured")
        ctx.load_cert_chain(CERT_FILE, KEY_FILE)
        if ROOT_CA:
            try:
                ctx.load_verify_locations(ROOT_CA)
            except Exception:
                # try loading as cadata
                with open(ROOT_CA, "rb") as f:
                    raw = f.read()
                ctx.load_verify_locations(cadata=raw)
        try:
            ctx.verify_mode = ssl.CERT_REQUIRED
        except Exception:
            pass
        c = MQTT.MQTT(
            broker=AWS_ENDPOINT,
            port=8883,
            client_id=client_id,
            socket_pool=pool,
            ssl_context=ctx,
            is_ssl=True,
            keep_alive=keepalive
        )
        return c
    except Exception as e:
        print("❌ mqtt_client._create_mqtt_client error:", e)
        return None
PY

# publisher.py
cat > "${BASE}/publisher.py" <<'PY'
# publisher.py
import gc
import json
from mqtt_client import _create_mqtt_client

_persistent_client = None
PUB_CLIENT_ID = None

def ensure_persistent(client):
    global _persistent_client
    _persistent_client = client

def publish(topic, message, qos=0, retain=False):
    global _persistent_client
    payload = message if isinstance(message, (bytes, bytearray)) else str(message)
    try:
        if _persistent_client:
            try:
                _persistent_client.publish(topic, payload, qos=qos, retain=retain)
                print(f"✅ Published (persistent) to {topic}: {payload}")
                return True
            except Exception as e:
                print("⚠️ persistent publish failed, falling back:", e)
        gc.collect()
        c = _create_mqtt_client(PUB_CLIENT_ID or "pico_pub")
        if c is None:
            raise RuntimeError("Failed to create short-lived MQTT client")
        c.connect()
        c.publish(topic, payload, qos=qos, retain=retain)
        c.disconnect()
        gc.collect()
        print(f"✅ Published (short) to {topic}: {payload}")
        return True
    except Exception as e:
        print("❌ publish error:", e)
        return False

def publish_json(topic, data, qos=0, retain=False):
    try:
        payload = json.dumps(data)
    except Exception:
        payload = str(data)
    return publish(topic, payload, qos=qos, retain=retain)
PY

# subscriber.py
cat > "${BASE}/subscriber.py" <<'PY'
# subscriber.py
import time
import json
from publisher import publish_json

_last_msg = {"topic": None, "payload": None, "ts": 0}
DEDUP_WINDOW = 2

def set_dedup_window(sec):
    global DEDUP_WINDOW
    DEDUP_WINDOW = float(sec)

def sub_callback(client_obj, topic, msg):
    global _last_msg
    try:
        now = time.monotonic()
        if (_last_msg["topic"] == topic and _last_msg["payload"] == msg
                and now - _last_msg["ts"] < DEDUP_WINDOW):
            print("⚠️ Duplicate message ignored")
            return
        _last_msg.update({"topic": topic, "payload": msg, "ts": now})
        print("📩 Message arrived:", topic, msg)
        try:
            data = json.loads(msg)
        except Exception:
            data = None
        # Basic command handling (extend as needed)
        parts = topic.rstrip('/').split('/')
        action = parts[-1] if parts else None
        if isinstance(data, dict) and data.get("action"):
            action = data.get("action")
        if action == "system" or topic.endswith("/cmd/system"):
            cmd = data.get("cmd") if isinstance(data, dict) else None
            if cmd == "status":
                publish_json(f"devices/{client_obj.client_id}/status", {"uptime": int(time.time()), "status": "ok"})
            elif cmd == "reboot":
                import microcontroller
                microcontroller.reset()
            else:
                print("▶ Unknown system command:", cmd)
        else:
            print("ℹ️ No handler for action:", action)
    except Exception as e:
        print("❌ sub_callback error:", e)
PY

# certs_utils.py
cat > "${BASE}/certs_utils.py" <<'PY'
# certs_utils.py
import os

def resolve_cert_paths(cfg):
    cert_dir = getattr(cfg, "CERT_DIR", "certs")
    cert_file = getattr(cfg, "CERT_FILE", None)
    key_file = getattr(cfg, "KEY_FILE", None)
    root_ca_file = getattr(cfg, "ROOT_CA_FILE", "AmazonRootCA1.pem")
    ca_at_root = getattr(cfg, "CA_AT_ROOT", False)

    if cert_file and not os.path.isabs(cert_file) and not cert_file.startswith(cert_dir + "/"):
        cert_file = os.path.join(cert_dir, cert_file)
    if key_file and not os.path.isabs(key_file) and not key_file.startswith(cert_dir + "/"):
        key_file = os.path.join(cert_dir, key_file)

    if ca_at_root:
        root_ca = "/" + root_ca_file.lstrip("/")
    else:
        root_ca = os.path.join(cert_dir, root_ca_file)
    return cert_file, key_file, root_ca
PY

# aws_test wrapper (compat)
cat > "${BASE}/aws_test.py" <<'PY'
# aws_test.py - compatibility wrapper that wires split modules
import config
from certs_utils import resolve_cert_paths
import mqtt_client, publisher, subscriber

def apply_config_to_aws_test():
    # mqtt_client globals
    mqtt_client.AWS_ENDPOINT = getattr(config, "AWS_ENDPOINT", mqtt_client.AWS_ENDPOINT)
    mqtt_client.CLIENT_ID = getattr(config, "MQTT_CLIENT_ID", getattr(config, "DEVICE_ID", mqtt_client.CLIENT_ID))
    cert_file, key_file, root_ca = resolve_cert_paths(config)
    mqtt_client.CERT_FILE = cert_file
    mqtt_client.KEY_FILE = key_file
    mqtt_client.ROOT_CA = root_ca

    # publisher
    publisher.PUB_CLIENT_ID = mqtt_client.CLIENT_ID + "_pub"

    # subscriber
    subscriber.set_dedup_window(getattr(config, "DEDUP_WINDOW", 2))

    print("✅ aws_test: configuration applied")
PY

chmod +x "${BASE}/make_aws_split.sh"
echo "Split modules created."
