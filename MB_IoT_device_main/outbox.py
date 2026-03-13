# outbox.py
import os, json

OUTBOX_FILE = "outbox.jsonl"
MAX_FILE_SIZE = 64 * 1024

def _ensure_file():
    if OUTBOX_FILE not in os.listdir():
        with open(OUTBOX_FILE, "w") as f:
            pass

def enqueue(topic, payload):
    _ensure_file()
    entry = {"topic": topic, "payload": payload}
    s = json.dumps(entry, separators=(",", ":"))
    with open(OUTBOX_FILE, "a") as f:
        f.write(s + "\n")
    _rotate_if_needed()

def peek_all():
    if OUTBOX_FILE not in os.listdir():
        return []
    items = []
    with open(OUTBOX_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    return items

def remove_first():
    if OUTBOX_FILE not in os.listdir():
        return
    with open(OUTBOX_FILE, "r") as f:
        lines = f.readlines()
    if not lines:
        return
    with open(OUTBOX_FILE, "w") as f:
        f.writelines(lines[1:])

def _rotate_if_needed():
    try:
        size = os.stat(OUTBOX_FILE)[6]
        if size > MAX_FILE_SIZE:
            i = 1
            while True:
                name = f"outbox.{i}.bak"
                if name not in os.listdir():
                    os.rename(OUTBOX_FILE, name)
                    break
                i += 1
            with open(OUTBOX_FILE, "w") as f:
                pass
    except Exception:
        pass