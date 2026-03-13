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
