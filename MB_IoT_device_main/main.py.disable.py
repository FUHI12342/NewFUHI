# main.py
# Robust main loop for CircuitPython (Raspberry Pi Pico 2 W)
# - Wi-Fi + AWS IoT MQTT publish
# - Django /api/iot/events/ にもセンサ＆ボタンイベントを送信
# - ボタン短押しでブザー鳴動＋button_short_pressイベント送信
# - 長押しでプロビジョニングモード＋button_long_pressイベント送信

import time
import json
import gc
import board
import busio
import digitalio
import microcontroller

import config
import aws_client

# Django 連携用設定（config.py に定義）
DJANGO_EVENTS_URL = getattr(config, "DJANGO_EVENTS_URL", None)
DJANGO_API_KEY = getattr(config, "DJANGO_API_KEY", None)

# MQTT 関連
import mqtt_client
import publisher
import subscriber

# sensors / actuators
from sensors.mq9 import MQ9
from sensors.light import LightSensor
from sensors.sound import SoundSensor
from sensors.pir import PIR
from actuators.buzzer import Buzzer

# IR receive helper (lazy init)
import ir_rx

# Optional LCD driver (lcd_display.py を lcd_driver エイリアスで使う)
try:
    import lcd_display as lcd_driver
except Exception:
    lcd_driver = None

# ------------------------
# Module-level globals
devices = {}
button = None
buzzer = None

# 最新のセンサー値をグローバルにキャッシュして、
# ボタン短押し時などに LCD 表示で使う
cached_sensors = {
    "mq9": None,
    "light": None,
    "sound": None,
    "temp": None,
    "hum": None,
}

# Default thresholds (can be overridden in config)
BUTTON_HOLD_SECONDS = getattr(config, "BUTTON_HOLD_SECONDS", 5)
BUTTON_ACTIVE_HIGH = getattr(config, "BUTTON_ACTIVE_HIGH", False)

# 測定間隔 / 送信間隔
SENSOR_READ_INTERVAL = getattr(config, "SENSOR_READ_INTERVAL", 3)   # 3秒ごとにセンサー読む
MQTT_PUBLISH_INTERVAL = getattr(config, "MQTT_PUBLISH_INTERVAL", 3) # 3秒ごとにMQTT送信
DJANGO_EVENT_INTERVAL = getattr(config, "DJANGO_EVENT_INTERVAL", 20) # 20秒ごとにDjangoへIoTイベント送信

# HTTP セッション（Django連携用）
_http_session = None


# ------------------------
# HTTP helper for Django

def get_http_session():
    """Lazy 初期化の HTTP セッション（CircuitPython adafruit_requests 用）"""
    global _http_session
    if _http_session is not None:
        return _http_session

    try:
        import wifi
        import socketpool
        import adafruit_requests

        pool = socketpool.SocketPool(wifi.radio)
        # HTTPなのでSSLコンテキストは None
        _http_session = adafruit_requests.Session(pool, None)
        print("HTTP session for Django created.")
    except Exception as e:
        print("Failed to create HTTP session:", e)
        _http_session = None
    return _http_session


def post_to_django(payload):
    """
    Django の /api/iot/events/ にセンサ値やボタンイベントを POST する。
    設定がない・エラーが出た場合でも main_loop は止めない。
    エラー時は HTTP セッションを破棄して次回再生成する。
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
            "X-API-KEY": DJANGO_API_KEY,
        }
        body = json.dumps(payload)
        print("POST to Django:", body)
        resp = sess.post(DJANGO_EVENTS_URL, data=body, headers=headers)
        try:
            print("Django POST status:", resp.status_code)
        finally:
            resp.close()
    except Exception as e:
        print("Django POST error:", e)
        # 壊れたセッションは捨てる
        _http_session = None


# ------------------------
# Helpers

def get_provision_pin():
    """Return a valid provision pin number or None if disabled/invalid."""
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
    """Create a DigitalInOut button or return None on error/invalid pin."""
    try:
        if pin_num is None:
            return None
        try:
            if int(pin_num) < 0:
                return None
        except Exception:
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
    """Wait until wifi.radio.ipv4_address is present and DNS resolves AWS endpoint."""
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
# Provisioning helpers

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


def provisioning_prompt_via_serial():
    print(
        'Provisioning prompt: paste JSON like '
        '{"ssid":"your_ssid","password":"your_password"}'
    )
    try:
        s = input()
        j = json.loads(s)
        ssid = j.get("ssid")
        pwd = j.get("password")
        if ssid and pwd:
            try:
                with open("config.py", "a") as f:
                    f.write(f'\nWIFI_SSID = "{ssid}"\nWIFI_PASSWORD = "{pwd}"\n')
                print("Saved credentials to config.py. Rebooting...")
                time.sleep(1)
                microcontroller.reset()
            except Exception as e:
                print("Failed to save credentials:", e)
        else:
            print("JSON missing ssid/password.")
    except Exception as e:
        print("Provisioning input error:", e)


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
    print(
        "To provision, run provisioning_prompt_via_serial() from REPL "
        "or update config.py via USB."
    )


def check_button():
    """
    ボタン押下の検出：
      - 短押し: ブザーを鳴らす + Django に button_short_press イベント送信
      - 長押し: プロビジョニングモード + button_long_press イベント送信
    """
    global button, buzzer, cached_sensors
    if not button:
        return

    try:
        active_high = getattr(config, "BUTTON_ACTIVE_HIGH", False)

        v = button.value
        pressed = v if active_high else (not v)
        if not pressed:
            return

        # デバウンス 30ms
        t0 = time.monotonic()
        stable = True
        while time.monotonic() - t0 < 0.03:
            try:
                v = button.value
                p = v if active_high else (not v)
            except Exception:
                p = False
            if not p:
                stable = False
                break
            time.sleep(0.005)
        if not stable:
            return

        # 押し続け時間を計測
        start = time.monotonic()
        while True:
            try:
                v = button.value
                p = v if active_high else (not v)
            except Exception:
                p = False
            if not p:
                break
            time.sleep(0.02)

        duration = time.monotonic() - start
        if duration < 0.05:
            return

        hold_sec = getattr(config, "BUTTON_HOLD_SECONDS", BUTTON_HOLD_SECONDS)
        device_id = getattr(config, "DEVICE_ID", "device")

        if duration >= hold_sec:
            event_type = "button_long_press"
            print(f"Button long press detected ({duration:.2f}s)")
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
            print(f"Button short press detected ({duration:.2f}s)")
            if buzzer:
                try:
                    buzzer.tone(1000, 300)
                except Exception:
                    try:
                        buzzer.beep(300)
                    except Exception as e:
                        print("Buzzer error (short):", e)

            # 短押し時に LCD に現在時刻とセンサー要約値を表示
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

        payload = {
            "device": device_id,
            "event_type": event_type,
            "pressed": True,
            "duration": duration,
            "ts": int(time.time()),
        }
        print("Posting button event to Django:", payload)
        post_to_django(payload)

        try:
            publisher.publish_json(
                getattr(config, "TOPIC_STATUS", f"devices/{device_id}/status"),
                payload,
            )
        except Exception as e:
            print("MQTT publish button event error:", e)

    except Exception as e:
        print("Button check error:", e)


# ------------------------
# Initialization

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
                # debug 引数なしで呼ぶ
                ir_rx.init(pin_num=ir_pin)
            except Exception as e:
                print("ir_rx init (ignored):", e)
    except Exception as e:
        print("ir_rx init check failed:", e)

    # LCD 初期化（あれば）
    if lcd_driver is not None:
        i2c = None

        # 試す候補: I2C1(GP7=SCL,GP6=SDA) → I2C0(GP5=SCL,GP4=SDA) の順
        candidates = [
            (board.GP7, board.GP6, "I2C1 (GP7=SCL, GP6=SDA)"),
            (board.GP5, board.GP4, "I2C0 (GP5=SCL, GP4=SDA)"),
        ]

        for scl, sda, name in candidates:
            try:
                print("Trying LCD on", name)
                cand = busio.I2C(scl, sda)
                locked = False
                t0 = time.monotonic()
                while True:
                    if cand.try_lock():
                        locked = True
                        break
                    if time.monotonic() - t0 > 1.0:
                        break
                    time.sleep(0.01)

                if not locked:
                    print("  could not lock", name)
                    continue

                try:
                    addrs = cand.scan()
                finally:
                    cand.unlock()

                print("  scan:", [hex(a) for a in addrs])

                # 何かしら I2C デバイスがいれば採用（特に 0x3e が有力）
                if 0x3e in addrs or len(addrs) > 0:
                    i2c = cand
                    print("  use this bus for LCD.")
                    break
            except Exception as e:
                print("  I2C init error on", name, ":", e)

        if i2c is None:
            print("LCD init skipped: no I2C device found")
        else:
            try:
                lcd_type = getattr(config, "LCD_TYPE", "char")  # "char" or "oled"
                if lcd_type == "char" and hasattr(lcd_driver, "init_char"):
                    lcd_driver.init_char(i2c, address=0x3e)
                elif lcd_type == "oled" and hasattr(lcd_driver, "init_oled"):
                    lcd_driver.init_oled(i2c)

                if hasattr(lcd_driver, "show_text"):
                    lcd_driver.show_text("IoT booting...")
            except Exception as e:
                print("LCD driver init failed:", e)

    # MQTT persistent client
    persistent_ok = False
    try:
        try:
            client = mqtt_client.create_mqtt_client()
        except Exception:
            client = getattr(mqtt_client, "_create_mqtt_client", lambda *a, **k: None)()
        if client is None:
            print("Failed to create persistent MQTT client")
            persistent_ok = False
        else:
            try:
                client.on_message = subscriber.sub_callback
            except Exception:
                pass
            try:
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
                print("Persistent MQTT connect failed:", e)
                persistent_ok = False
    except Exception as e:
        print("MQTT persistent client setup error:", e)
        persistent_ok = False

    devices.update(
        {
            "mq9": mq9,
            "light": light,
            "sound": sound,
            "pir": pir,
        }
    )

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
            publisher.publish_json(
                getattr(
                    config,
                    "TOPIC_STATUS",
                    f"devices/{getattr(config, 'DEVICE_ID', 'device')}/status",
                ),
                {"ir": res, "ts": int(time.time())},
            )
            print("Published IR:", res)
    except Exception as e:
        print("IR monitor error:", e)


# ------------------------
# Main loop

def main_loop():
    global devices, cached_sensors
    # 3秒ごとにセンサー読み取り
    last_read_ts = 0
    # MQTT送信（既定3秒ごと）
    last_mqtt_publish_ts = 0
    # Django IoTイベント送信（既定20秒ごと）
    last_django_publish_ts = 0

    # 起動時にキャッシュをクリア
    for k in cached_sensors.keys():
        cached_sensors[k] = None

    while True:
        try:
            check_button()
        except Exception as e:
            print("Button check error:", e)

        now = time.monotonic()

        # ---- センサー読み取り（3秒ごと）----
        if now - last_read_ts >= SENSOR_READ_INTERVAL:
            try:
                mq9_dev = devices.get("mq9")
                light_dev = devices.get("light")
                sound_dev = devices.get("sound")

                cached_sensors["mq9"] = mq9_dev.read() if mq9_dev else None
                cached_sensors["light"] = light_dev.read() if light_dev else None
                cached_sensors["sound"] = sound_dev.read() if sound_dev else None
                # temp / hum は今は None （将来 DHT など追加予定）

                print(
                    "Sampled sensors:",
                    {
                        "mq9": cached_sensors["mq9"],
                        "light": cached_sensors["light"],
                        "sound": cached_sensors["sound"],
                    },
                )

                # センサー読み取りのタイミングで LCD に現在値を表示（あれば）
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

        # ---- MQTT送信処理（既定3秒ごと）----
        if now - last_mqtt_publish_ts >= MQTT_PUBLISH_INTERVAL:
            try:
                device_id = getattr(config, "DEVICE_ID", "device")
                mqtt_payload = {
                    "mq9": cached_sensors["mq9"],
                    "sound": cached_sensors["sound"],
                    "temp": cached_sensors["temp"],
                    "hum": cached_sensors["hum"],
                    "ts": int(time.time()),
                    "device": device_id,
                    "light": cached_sensors["light"],
                }
                print("Publishing sensors to MQTT:", mqtt_payload)

                publisher.publish_json(
                    getattr(
                        config,
                        "TOPIC_SENSOR",
                        f"devices/{device_id}/sensors",
                    ),
                    mqtt_payload,
                )
                print(
                    "✅ Published (persistent) to "
                    f"{getattr(config, 'TOPIC_SENSOR', 'devices/.../sensors')}: "
                    f"{json.dumps(mqtt_payload)}"
                )
            except Exception as e:
                print("Sensor MQTT publish error:", e)
            last_mqtt_publish_ts = now

        # ---- Django へのIoTイベント送信（既定20秒ごと）----
        if now - last_django_publish_ts >= DJANGO_EVENT_INTERVAL:
            try:
                device_id = getattr(config, "DEVICE_ID", "device")
                django_payload = {
                    "device": device_id,
                    "event_type": "sensor",
                    "mq9": cached_sensors["mq9"],
                    "sound": cached_sensors["sound"],
                    "temp": cached_sensors["temp"],
                    "hum": cached_sensors["hum"],
                    "light": cached_sensors["light"],
                    "ts": int(time.time()),
                }
                print("Posting sensors to Django (every 20s):", django_payload)
                post_to_django(django_payload)
            except Exception as e:
                print("Sensor Django post error:", e)
            last_django_publish_ts = now

        # ---- IR ＆ MQTT ループ ----
        try:
            monitor_ir_and_publish_once()
        except Exception as e:
            print("IR monitor error:", e)

        try:
            c = getattr(publisher, "_persistent_client", None)
            if c and hasattr(c, "loop"):
                try:
                    c.loop()
                except Exception as e:
                    print("MQTT loop warning:", e)
                    try:
                        if hasattr(c, "reconnect"):
                            c.reconnect()
                            print("MQTT reconnected")
                    except Exception as re:
                        print("MQTT reconnect failed:", re)
        except Exception:
            pass

        try:
            gc.collect()
        except Exception:
            pass
        time.sleep(0.1)


# ------------------------
# Run

if __name__ == "__main__":
    state = init_all()

    try:
        if state:
            if state.get("buzzer") is not None:
                buzzer = state.get("buzzer")
            if state.get("button") is not None:
                button = state.get("button")
    except Exception:
        pass

    try:
        provisioning_window(
            button,
            hold_seconds=getattr(
                config, "BUTTON_HOLD_SECONDS", BUTTON_HOLD_SECONDS
            ),
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