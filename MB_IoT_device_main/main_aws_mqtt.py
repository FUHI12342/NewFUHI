# main.py (final / Django-compatible)

import time
import json
import gc
import board
import busio
import digitalio
import microcontroller

import config
import aws_client

# Django integration (from config.py)
DJANGO_EVENTS_URL = getattr(config, "DJANGO_EVENTS_URL", None)
DJANGO_API_KEY = getattr(config, "DJANGO_API_KEY", None)

# MQTT
import mqtt_client
import publisher
import subscriber

# sensors / actuators
from sensors.mq9 import MQ9
from sensors.light import LightSensor
from sensors.sound import SoundSensor
from sensors.pir import PIR
from actuators.buzzer import Buzzer

# IR
import ir_rx

# Optional LCD driver
try:
    import lcd_display as lcd_driver
except Exception:
    lcd_driver = None

# ------------------------
# Globals
devices = {}
button = None
buzzer = None

cached_sensors = {
    "mq9": None,
    "light": None,
    "sound": None,
    "temp": None,
    "hum": None,
}

BUTTON_HOLD_SECONDS = getattr(config, "BUTTON_HOLD_SECONDS", 5)
BUTTON_ACTIVE_HIGH = getattr(config, "BUTTON_ACTIVE_HIGH", False)

ENABLE_RUNTIME_PROVISION_LONG_PRESS = getattr(
    config, "ENABLE_RUNTIME_PROVISION_LONG_PRESS", False
)

SENSOR_READ_INTERVAL = getattr(config, "SENSOR_READ_INTERVAL", 3)
MQTT_PUBLISH_INTERVAL = getattr(config, "MQTT_PUBLISH_INTERVAL", 30)
DJANGO_EVENT_INTERVAL = getattr(config, "DJANGO_EVENT_INTERVAL", 30)

_http_session = None


# ------------------------
# Django HTTP helper

def get_http_session():
    """Lazy init HTTP Session (CircuitPython adafruit_requests)"""
    global _http_session
    if _http_session is not None:
        return _http_session

    try:
        import wifi
        import socketpool
        import adafruit_requests

        pool = socketpool.SocketPool(wifi.radio)
        # HTTPなのでSSLコンテキストNone
        _http_session = adafruit_requests.Session(pool, None)
        print("HTTP session for Django created.")
    except Exception as e:
        print("Failed to create HTTP session:", e)
        _http_session = None

    return _http_session


def build_django_payload(event_type, extra=None):
    """
    ✅ Djangoの IoTEventAPIView 仕様に完全準拠
    必須: device, event_type
    任意: mq9/light/sound/temp/hum/ts
    """
    device_id = getattr(config, "DEVICE_ID", "device")
    payload = {
        "device": device_id,
        "event_type": event_type,
        "mq9": cached_sensors.get("mq9"),
        "light": cached_sensors.get("light"),
        "sound": cached_sensors.get("sound"),
        "pir": cached_sensors.get("pir"),
        "temp": cached_sensors.get("temp"),
        "hum": cached_sensors.get("hum"),
        "ts": int(time.time()),
    }
    if isinstance(extra, dict):
        payload.update(extra)
    return payload


def post_to_django(payload):
    """
    Django /api/iot/events/ に POST（失敗しても止めない）
    """
    global _http_session

    if not DJANGO_EVENTS_URL or not DJANGO_API_KEY:
        return

    try:
        sess = get_http_session()
        if not sess:
            return

        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": DJANGO_API_KEY,  # 必須
        }
        body = json.dumps(payload)
        print("POST to Django:", body)

        resp = sess.post(DJANGO_EVENTS_URL, data=body, headers=headers)
        try:
            print("Django POST status:", resp.status_code)
            try:
                # デバッグ用（不要なら消してOK）
                print("Django response:", resp.text)
            except Exception:
                pass
        finally:
            resp.close()

    except Exception as e:
        print("Django POST error:", e)
        _http_session = None


# ------------------------
# Helpers

def get_provision_pin():
    try:
        prov = getattr(config, "PROVISION_BUTTON_GP", None)
        if prov is None:
            return None
        prov_i = int(prov)
        if prov_i < 0:
            return None
        return prov_i
    except Exception:
        return None


def create_button(pin_num):
    try:
        if pin_num is None:
            return None
        if int(pin_num) < 0:
            return None
        pin = getattr(board, f"GP{int(pin_num)}")
        b = digitalio.DigitalInOut(pin)
        b.direction = digitalio.Direction.INPUT
        try:
            b.pull = digitalio.Pull.UP
        except Exception:
            pass
        return b
    except Exception as e:
        print("Button init failed:", e)
        return None


def wait_for_wifi_and_dns(timeout_s=60):
    try:
        import wifi
        import socketpool
    except Exception as e:
        print("Wi-Fi modules not available:", e)
        return False

    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        try:
            ip = getattr(wifi.radio, "ipv4_address", None)
            if ip:
                try:
                    pool = socketpool.SocketPool(wifi.radio)
                    pool.getaddrinfo(config.AWS_ENDPOINT, 8883)
                    print("Wi-Fi and DNS ready, IP:", ip)
                    return True
                except Exception as e:
                    print("DNS not ready yet:", e)
            else:
                print("Wi-Fi not ready yet")
        except Exception as e:
            print("Wi-Fi check error:", e)
        time.sleep(1)

    print("Wi-Fi/DNS wait timeout")
    return False


# ------------------------
# Provisioning

def provisioning_window(btn, hold_seconds=None, timeout_s=None):
    if btn is None:
        return
    if hold_seconds is None:
        hold_seconds = getattr(config, "BUTTON_HOLD_SECONDS", BUTTON_HOLD_SECONDS)
    if timeout_s is None:
        timeout_s = getattr(config, "PROVISIONING_TIMEOUT", 10)

    if timeout_s <= 0:
        return

    print(
        "Startup provisioning window: hold button for "
        f"{hold_seconds}s within {timeout_s}s to enter provisioning."
    )
    start_total = time.monotonic()
    while time.monotonic() - start_total < timeout_s:
        try:
            val = btn.value
            pressed = val if BUTTON_ACTIVE_HIGH else (not val)
            if pressed:
                press_start = time.monotonic()
                while True:
                    try:
                        val = btn.value
                        pressed = val if BUTTON_ACTIVE_HIGH else (not val)
                    except Exception:
                        pressed = False
                    if not pressed or (time.monotonic() - press_start) >= hold_seconds:
                        break
                    time.sleep(0.05)
                if pressed and (time.monotonic() - press_start) >= hold_seconds:
                    enter_provisioning_mode()
                    return
        except Exception:
            break
        time.sleep(0.05)


def enter_provisioning_mode():
    print("Entering Wi-Fi provisioning mode...")
    if lcd_driver:
        try:
            if hasattr(lcd_driver, "show_text_lines"):
                lcd_driver.show_text_lines("Wi-Fi setup mode")
            elif hasattr(lcd_driver, "show_sensors"):
                lcd_driver.show_sensors({"MODE": "WiFiSetup"})
        except Exception:
            print("LCD display failed (continuing)")
    print("Provisioning: update config.py via USB or serial.")


# ------------------------
# Button

def check_button():
    global button, buzzer, cached_sensors
    if not button:
        return

    try:
        active_high = getattr(config, "BUTTON_ACTIVE_HIGH", False)

        v = button.value
        pressed = v if active_high else (not v)
        if not pressed:
            return

        # debounce 30ms
        t0 = time.monotonic()
        stable = True
        while time.monotonic() - t0 < 0.03:
            v = button.value
            p = v if active_high else (not v)
            if not p:
                stable = False
                break
            time.sleep(0.005)
        if not stable:
            return

        # measure press duration
        start = time.monotonic()
        while True:
            v = button.value
            p = v if active_high else (not v)
            if not p:
                break
            time.sleep(0.02)

        duration = time.monotonic() - start
        if duration < 0.05:
            return

        hold_sec = float(getattr(config, "BUTTON_HOLD_SECONDS", BUTTON_HOLD_SECONDS) or BUTTON_HOLD_SECONDS)
        if hold_sec < 5.0:
            hold_sec = 5.0

        if duration >= hold_sec:
            event_type = "button_long_press"
            print(f"Button long press ({duration:.2f}s)")
            if ENABLE_RUNTIME_PROVISION_LONG_PRESS:
                enter_provisioning_mode()
            if buzzer:
                try:
                    buzzer.tone(800, 400)
                except Exception:
                    try:
                        buzzer.beep(400)
                    except Exception as e:
                        print("Buzzer error (long):", e)
        else:
            event_type = "button_short_press"
            print(f"Button short press ({duration:.2f}s)")
            if buzzer:
                try:
                    buzzer.tone(1000, 300)
                except Exception:
                    try:
                        buzzer.beep(300)
                    except Exception as e:
                        print("Buzzer error (short):", e)

            # LCD display
            try:
                if lcd_driver is not None and hasattr(lcd_driver, "show_time_and_sensors"):
                    now_t = time.localtime()
                    time_str = "{:02d}:{:02d}".format(now_t.tm_hour, now_t.tm_min)
                    lcd_driver.show_time_and_sensors(
                        time_str,
                        cached_sensors.get("mq9"),
                        cached_sensors.get("light"),
                        cached_sensors.get("sound"),
                        cached_sensors.get("temp"),
                        cached_sensors.get("hum"),
                    )
            except Exception as e:
                print("LCD update error:", e)

        # ✅ Djangoへ：仕様通りにフラットで送る
        django_payload = build_django_payload(
            event_type=event_type,
            extra={
                # duration 等を保存したい場合は、今のDjango実装では取り込まれない。
                # (将来的にDjango側をpayload受けにしたらここに入れてOK)
                "ts": int(time.time()),
            },
        )
        post_to_django(django_payload)

        # MQTTにも流す（ここは自由。従来どおり詳細を載せてもOK）
        mqtt_ev = {
            "device": django_payload["device"],
            "event_type": event_type,
            "duration": duration,
            "pressed": True,
            "sensors": {
                "mq9": cached_sensors.get("mq9"),
                "light": cached_sensors.get("light"),
                "sound": cached_sensors.get("sound"),
                "temp": cached_sensors.get("temp"),
                "hum": cached_sensors.get("hum"),
            },
            "ts": int(time.time()),
        }
        try:
            publisher.publish_json(getattr(config, "TOPIC_STATUS"), mqtt_ev)
        except Exception as e:
            print("MQTT publish button event error:", e)

    except Exception as e:
        print("Button check error:", e)


# ------------------------
# Init

def init_all():
    global devices, button, buzzer
    print("Initializing devices and AWS config...")

    try:
        aws_client.apply_config()
    except Exception as e:
        print("aws_client.apply_config error:", e)

    # Buzzer
    try:
        buzzer = Buzzer(pin_num=getattr(config, "BUZZER_GP", 20))
        try:
            buzzer.init()
        except Exception:
            pass
    except Exception as e:
        print("Buzzer init failed:", e)
        buzzer = None

    # Button
    try:
        prov_pin = get_provision_pin()
        if prov_pin is not None:
            button = create_button(prov_pin)
        else:
            button = create_button(getattr(config, "BUTTON_GP", None))
    except Exception as e:
        print("Button setup error:", e)
        button = None

    # Wi-Fi & DNS
    try:
        import wifi
        if not getattr(wifi.radio, "ipv4_address", None):
            ssid = getattr(config, "WIFI_SSID", None)
            pwd = getattr(config, "WIFI_PASSWORD", None)
            if ssid and pwd:
                print("Attempting wifi connect...")
                try:
                    wifi.radio.connect(ssid, pwd)
                except Exception as e:
                    print("wifi connect attempt error:", e)
        wait_for_wifi_and_dns(timeout_s=getattr(config, "WIFI_DNS_WAIT_S", 60))
    except Exception as e:
        print("Wi-Fi/DNS pre-check error:", e)

    # Sensors
    try:
        mq9 = MQ9(pin_num=getattr(config, "A0_GP", 26))
    except Exception as e:
        print("MQ9 init error:", e)
        mq9 = None
    try:
        light = LightSensor(pin_num=getattr(config, "A1_GP", 27))
    except Exception as e:
        print("Light init error:", e)
        light = None
    try:
        sound = SoundSensor(pin_num=getattr(config, "A2_GP", 28))
    except Exception as e:
        print("Sound init error:", e)
        sound = None
    try:
        pir = PIR(pin_num=getattr(config, "PIR_GP", 17))
    except Exception as e:
        print("PIR init error:", e)
        pir = None

    # DHT I2C sensor
    try:
        import dht_i2c
        dht_sensor = dht_i2c.init(channel=None)  # Direct connection, no mux yet
    except Exception as e:
        print("DHT init error:", e)
        dht_sensor = None

    for dev in (mq9, light, sound, pir, buzzer):
        if dev:
            try:
                dev.init()
            except Exception as e:
                print("init error:", e)

    # IR RX
    try:
        ir_pin = getattr(config, "IR_RX_PIN", None)
        if isinstance(ir_pin, int):
            try:
                ir_rx.init(pin_num=ir_pin)
            except Exception as e:
                print("ir_rx init (ignored):", e)
    except Exception as e:
        print("ir_rx init check failed:", e)

    # LCD init (updated to use centralized I2C)
    if lcd_driver is not None:
        try:
            print("Init Grove LCD on I2C1 (SCL=GP7, SDA=GP6)")
            # Use centralized I2C bus, channel=None for direct connection (no mux yet)
            if hasattr(lcd_driver, "init_grove_lcd"):
                lcd_driver.init_grove_lcd(channel=None, cols=16, rows=2)
            else:
                # Fallback for old API
                import i2c_bus
                i2c1 = i2c_bus.get_i2c()
                if hasattr(lcd_driver, "init_char"):
                    lcd_driver.init_char(i2c1, address=0x3e)
            if hasattr(lcd_driver, "show_text"):
                lcd_driver.show_text("IoT booting...")
        except Exception as e:
            print("LCD init failed:", e)

    # MQTT persistent client
    persistent_ok = False
    try:
        client = mqtt_client.create_mqtt_client()
        client.on_message = subscriber.sub_callback
        retries = getattr(config, "MQTT_CONNECT_RETRIES", 5)
        delay = getattr(config, "MQTT_CONNECT_RETRY_DELAY", 2)
        connected = False
        for i in range(retries):
            try:
                print("MQTT connect attempt", i + 1)
                client.connect()
                connected = True
                break
            except Exception as e:
                print("Persistent MQTT connect attempt failed:", e)
                time.sleep(delay)
        if connected:
            publisher.ensure_persistent(client)
            print("Persistent MQTT client connected")
            persistent_ok = True
        else:
            print("Persistent MQTT connect failed after retries")
            persistent_ok = False
    except Exception as e:
        print("MQTT persistent client setup error:", e)
        persistent_ok = False

    devices.update({"mq9": mq9, "light": light, "sound": sound, "pir": pir})

    return {
        "mq9": mq9,
        "light": light,
        "sound": sound,
        "pir": pir,
        "buzzer": buzzer,
        "button": button,
        "mqtt_client_ok": persistent_ok,
    }


# ------------------------
# IR monitor

def monitor_ir_and_publish_once():
    try:
        res = ir_rx.read_code(timeout_ms=1200)
        if res:
            # MQTTへ（Djangoへ送るなら event_type="ir" で build_django_payload() してpostでもOK）
            mqtt_ev = {
                "device": getattr(config, "DEVICE_ID", "device"),
                "event_type": "ir",
                "ir": res,
                "ts": int(time.time()),
            }
            publisher.publish_json(getattr(config, "TOPIC_STATUS"), mqtt_ev)
            print("Published IR:", res)
    except Exception as e:
        print("IR monitor error:", e)


# ------------------------
# Main loop

def main_loop():
    global devices, cached_sensors
    last_read_ts = 0
    last_mqtt_publish_ts = 0
    last_django_publish_ts = 0

    for k in cached_sensors.keys():
        cached_sensors[k] = None

    while True:
        # button
        check_button()

        now = time.monotonic()

        # ---- read sensors ----
        if now - last_read_ts >= SENSOR_READ_INTERVAL:
            try:
                mq9_dev = devices.get("mq9")
                light_dev = devices.get("light")
                sound_dev = devices.get("sound")

                cached_sensors["mq9"] = mq9_dev.read() if mq9_dev else None
                cached_sensors["light"] = light_dev.read() if light_dev else None
                cached_sensors["sound"] = sound_dev.read() if sound_dev else None

                # PIR motion sensor
                pir_dev = devices.get("pir")
                if pir_dev:
                    pir_val = pir_dev.read()
                    cached_sensors["pir"] = pir_val
                else:
                    cached_sensors["pir"] = None

                # DHT temperature/humidity
                try:
                    import dht_i2c
                    temp, hum = dht_i2c.read()
                    cached_sensors["temp"] = temp
                    cached_sensors["hum"] = hum
                except Exception as e:
                    print("DHT read error:", e)
                    cached_sensors["temp"] = None
                    cached_sensors["hum"] = None

                print("Sampled sensors:", cached_sensors)

                # LCD periodic update
                try:
                    if lcd_driver is not None and hasattr(lcd_driver, "show_time_and_sensors"):
                        now_t = time.localtime()
                        time_str = "{:02d}:{:02d}".format(now_t.tm_hour, now_t.tm_min)
                        lcd_driver.show_time_and_sensors(
                            time_str,
                            cached_sensors.get("mq9"),
                            cached_sensors.get("light"),
                            cached_sensors.get("sound"),
                            cached_sensors.get("temp"),
                            cached_sensors.get("hum"),
                        )
                except Exception as e:
                    print("LCD periodic update error:", e)

            except Exception as e:
                print("Sensor read error:", e)

            last_read_ts = now

        # ---- publish MQTT ----
        if now - last_mqtt_publish_ts >= MQTT_PUBLISH_INTERVAL:
            try:
                device_id = getattr(config, "DEVICE_ID", "device")
                mqtt_payload = {
                    "device": device_id,
                    "mq9": cached_sensors.get("mq9"),
                    "light": cached_sensors.get("light"),
                    "sound": cached_sensors.get("sound"),
                    "pir": cached_sensors.get("pir"),
                    "temp": cached_sensors.get("temp"),
                    "hum": cached_sensors.get("hum"),
                    "ts": int(time.time()),
                }
                publisher.publish_json(getattr(config, "TOPIC_SENSOR"), mqtt_payload)
                print("✅ Published to MQTT:", mqtt_payload)
            except Exception as e:
                print("Sensor MQTT publish error:", e)

            last_mqtt_publish_ts = now

        # ---- post Django ----
        if now - last_django_publish_ts >= DJANGO_EVENT_INTERVAL:
            try:
                django_payload = build_django_payload(event_type="sensor")
                print("Posting sensors to Django:", django_payload)
                post_to_django(django_payload)
            except Exception as e:
                print("Sensor Django post error:", e)

            last_django_publish_ts = now

        # ---- IR + MQTT loop ----
        monitor_ir_and_publish_once()

        try:
            c = getattr(publisher, "_persistent_client", None)
            if c and hasattr(c, "loop"):
                c.loop()
        except Exception as e:
            print("MQTT loop warning:", e)
            try:
                if hasattr(c, "reconnect"):
                    c.reconnect()
                    print("MQTT reconnected")
            except Exception as re:
                print("MQTT reconnect failed:", re)

        try:
            gc.collect()
        except Exception:
            pass

        time.sleep(0.1)


# ------------------------
# Run

if __name__ == "__main__":
    init_all()

    try:
        provisioning_window(
            button,
            hold_seconds=getattr(config, "BUTTON_HOLD_SECONDS", BUTTON_HOLD_SECONDS),
            timeout_s=getattr(config, "PROVISIONING_TIMEOUT", 10),
        )
    except Exception as e:
        print("Provisioning check error:", e)

    try:
        main_loop()
    except Exception as e:
        print("Fatal error in main_loop:", e)
        try:
            time.sleep(1)
            microcontroller.reset()
        except Exception:
            pass