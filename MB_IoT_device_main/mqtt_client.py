# mqtt_client.py
import ssl
import socketpool
import wifi
import adafruit_minimqtt.adafruit_minimqtt as MQTT

# Configurable globals (set by aws_test wrapper or config bridge)
AWS_ENDPOINT = None
CLIENT_ID = "pico_client"
CERT_FILE = None
KEY_FILE = None
ROOT_CA = None

# --- begin: config bridge (auto-insert) ---
try:
    import config
    AWS_ENDPOINT = getattr(config, "AWS_ENDPOINT", AWS_ENDPOINT)
    CLIENT_ID    = getattr(config, "CLIENT_ID", CLIENT_ID)
    CERT_FILE    = getattr(config, "CERT_FILE", CERT_FILE)
    KEY_FILE     = getattr(config, "KEY_FILE", KEY_FILE)
    ROOT_CA      = getattr(config, "ROOT_CA", ROOT_CA)
except Exception:
    pass
# --- end: config bridge ---

def _create_mqtt_client(client_id=CLIENT_ID, keepalive=60):
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
                try:
                    with open(ROOT_CA, "rb") as f:
                        raw = f.read()
                    ctx.load_verify_locations(cadata=raw)
                except Exception as e:
                    print("⚠️ mqtt_client: failed to load ROOT_CA:", e)
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

def create_mqtt_client(cfg=None, client_id=None, keepalive=60):
    global AWS_ENDPOINT, CERT_FILE, KEY_FILE, ROOT_CA, CLIENT_ID
    saved = (AWS_ENDPOINT, CERT_FILE, KEY_FILE, ROOT_CA, CLIENT_ID)
    try:
        if cfg is not None:
            try:
                AWS_ENDPOINT = getattr(cfg, "AWS_ENDPOINT", AWS_ENDPOINT)
                CLIENT_ID    = getattr(cfg, "CLIENT_ID", CLIENT_ID)
                CERT_FILE    = getattr(cfg, "CERT_FILE", CERT_FILE)
                KEY_FILE     = getattr(cfg, "KEY_FILE", KEY_FILE)
                ROOT_CA      = getattr(cfg, "ROOT_CA", ROOT_CA)
            except Exception:
                try:
                    AWS_ENDPOINT = cfg.get("AWS_ENDPOINT", AWS_ENDPOINT)
                    CLIENT_ID    = cfg.get("CLIENT_ID", CLIENT_ID)
                    CERT_FILE    = cfg.get("CERT_FILE", CERT_FILE)
                    KEY_FILE     = cfg.get("KEY_FILE", KEY_FILE)
                    ROOT_CA      = cfg.get("ROOT_CA", ROOT_CA)
                except Exception:
                    pass
        cid = client_id if client_id is not None else CLIENT_ID
        return _create_mqtt_client(client_id=cid, keepalive=keepalive)
    finally:
        AWS_ENDPOINT, CERT_FILE, KEY_FILE, ROOT_CA, CLIENT_ID = saved

def certs_ok():
    try:
        with open(CERT_FILE, "rb"):
            pass
        with open(KEY_FILE, "rb"):
            pass
        return True
    except Exception as e:
        print("mqtt_client.certs_ok check failed:", e)
        return False
