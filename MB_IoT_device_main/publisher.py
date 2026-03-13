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
