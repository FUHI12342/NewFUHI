# publisher_helper.py
import time, json
import publisher
import outbox

MAX_RETRIES = 5
BASE_BACKOFF = 0.5
MAX_BACKOFF = 8.0
LOG_PREFIX = "[PUBLISH]"

def _log(*args):
    try:
        print(LOG_PREFIX, *args)
    except Exception:
        pass

def publish_with_retry(topic, payload, persistent=True, max_retries=MAX_RETRIES):
    data = payload if isinstance(payload, dict) else {"payload": payload}
    attempt = 0
    backoff = BASE_BACKOFF
    last_exc = None

    if not hasattr(publisher, "publish_json"):
        _log("publish_json not available in publisher module")
        outbox.enqueue(topic, data)
        return False

    while attempt <= max_retries:
        attempt += 1
        try:
            _log("attempt", attempt, "publish to", topic, "persistent=", persistent)
            ok = publisher.publish_json(topic, data) if persistent else publisher.publish(topic, data)
            if ok:
                _log("Published", "topic:", topic, "payload:", json.dumps(data))
                return True
            else:
                _log("publish_json returned False, will retry", "attempt:", attempt)
        except Exception as e:
            last_exc = e
            _log("publish exception:", repr(e), "attempt:", attempt)

        if attempt <= max_retries:
            _log("backoff sleeping", backoff, "s")
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)

    _log("Max retries reached, enqueueing to outbox:", topic)
    try:
        outbox.enqueue(topic, data)
    except Exception as e:
        _log("Failed to enqueue to outbox:", e)
    _log("Last exception:", repr(last_exc))
    return False

def flush_outbox_once():
    _log("flush_outbox_once start")
    items = outbox.peek_all()
    if not items:
        _log("outbox empty")
        return
    for idx, item in enumerate(items):
        topic = item.get("topic")
        payload = item.get("payload")
        _log("flushing item", idx, "topic:", topic)
        ok = publish_with_retry(topic, payload, persistent=True, max_retries=2)
        if ok:
            outbox.remove_first()
            _log("flushed and removed item", idx)
        else:
            _log("failed to flush item", idx, "stop further attempts this cycle")
            break