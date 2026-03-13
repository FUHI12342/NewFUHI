#!/usr/bin/env bash
set -e

BASE="$(pwd)"
echo "Creating project skeleton in ${BASE}"

# ディレクトリ
mkdir -p "${BASE}/sensors"
mkdir -p "${BASE}/actuators"
mkdir -p "${BASE}/lib"
mkdir -p "${BASE}/certs"

# code.py (エントリポイント)
cat > "${BASE}/code.py" <<'PY'
# code.py - minimal entrypoint
import main
if __name__ == "__main__":
    main.main()
PY

# main.py (実動ロジックの起点)
cat > "${BASE}/main.py" <<'PY'
# main.py - minimal runtime
import time
import config
import aws_client
from sensors.mq9 import MQ9
from sensors.light import LightSensor
from sensors.sound import SoundSensor
from actuators.buzzer import Buzzer

def main():
    print("Starting main...")
    aws_client.apply_config()
    # init devices
    mq9 = MQ9(pin_num=config.A0_GP); mq9.init()
    light = LightSensor(pin_num=config.A1_GP); light.init()
    sound = SoundSensor(pin_num=config.A2_GP); sound.init()
    buz = Buzzer(pin_num=config.BUZZER_GP); buz.init()
    # quick loop
    for _ in range(3):
        payload = {
            "mq9": mq9.read(),
            "light": light.read(),
            "sound": sound.read(),
            "ts": int(time.time())
        }
        print("Publish:", payload)
        aws_client.publish_json(config.TOPIC_SENSOR, payload)
        time.sleep(2)
    print("Main finished.")
PY

# config.py (最小)
cat > "${BASE}/config.py" <<'PY'
# config.py - minimal settings
WIFI_SSID = ""
WIFI_PASSWORD = ""
DEVICE_ID = "Ace1"
AWS_ENDPOINT = ""
CERT_DIR = "certs"
CERT_FILE = "device-cert.der"
KEY_FILE = "device-private-rsa.der"
ROOT_CA_FILE = "AmazonRootCA1.pem"
CA_AT_ROOT = False
TOPIC_SENSOR = f"devices/{DEVICE_ID}/sensors"
# pin mapping
A0_GP = 26
A1_GP = 27
A2_GP = 28
BUTTON_GP = 16
PIR_GP = 17
BUZZER_GP = 20
I2C_SDA_GP = 4
I2C_SCL_GP = 5
SENSOR_PUBLISH_INTERVAL = 10
PY

# aws_client.py (薄いラッパー)
cat > "${BASE}/aws_client.py" <<'PY'
# aws_client.py - thin wrapper around aws_test
import aws_test, json
def apply_config():
    try:
        aws_test.apply_config_to_aws_test()
    except Exception as e:
        print("aws_client.apply_config error:", e)

def ensure_connected():
    try:
        return aws_test.ensure_client_connected()
    except Exception:
        return aws_test.check_connection()

def publish_json(topic, data):
    try:
        return aws_test.publish(topic, json.dumps(data))
    except Exception:
        return aws_test.publish(topic, str(data))
PY

# sensors/__init__.py
cat > "${BASE}/sensors/__init__.py" <<'PY'
# sensors package
PY

# sensors/mq9.py
cat > "${BASE}/sensors/mq9.py" <<'PY'
import analogio, board
class MQ9:
    def __init__(self, pin_num=26):
        self._pin = getattr(board, f"GP{pin_num}")
        self._adc = None
    def init(self):
        try:
            self._adc = analogio.AnalogIn(self._pin)
            return True
        except Exception as e:
            print("MQ9 init failed:", e); self._adc=None; return False
    def read(self):
        return int(self._adc.value) if self._adc else None
    def deinit(self):
        try:
            if self._adc: self._adc.deinit()
        except Exception: pass
PY

# sensors/light.py
cat > "${BASE}/sensors/light.py" <<'PY'
import analogio, board
class LightSensor:
    def __init__(self, pin_num=27):
        self._pin = getattr(board, f"GP{pin_num}")
        self._adc = None
    def init(self):
        try:
            self._adc = analogio.AnalogIn(self._pin); return True
        except Exception as e:
            print("Light init failed:", e); self._adc=None; return False
    def read(self):
        return int(self._adc.value) if self._adc else None
    def deinit(self):
        try:
            if self._adc: self._adc.deinit()
        except Exception: pass
PY

# sensors/sound.py
cat > "${BASE}/sensors/sound.py" <<'PY'
import analogio, board
class SoundSensor:
    def __init__(self, pin_num=28):
        self._pin = getattr(board, f"GP{pin_num}")
        self._adc = None
    def init(self):
        try:
            self._adc = analogio.AnalogIn(self._pin); return True
        except Exception as e:
            print("Sound init failed:", e); self._adc=None; return False
    def read(self):
        return int(self._adc.value) if self._adc else None
    def deinit(self):
        try:
            if self._adc: self._adc.deinit()
        except Exception: pass
PY

# sensors/pir.py (minimal)
cat > "${BASE}/sensors/pir.py" <<'PY'
import digitalio, board
class PIR:
    def __init__(self, pin_num=17):
        self._pin = getattr(board, f"GP{pin_num}")
        self._dio = None
    def init(self):
        try:
            self._dio = digitalio.DigitalInOut(self._pin)
            self._dio.direction = digitalio.Direction.INPUT
            try: self._dio.pull = digitalio.Pull.DOWN
            except Exception: pass
            return True
        except Exception as e:
            print("PIR init failed:", e); self._dio=None; return False
    def read(self):
        return bool(self._dio.value) if self._dio else None
    def deinit(self):
        try:
            if self._dio: self._dio.deinit()
        except Exception: pass
PY

# sensors/dht_i2c.py (placeholder)
cat > "${BASE}/sensors/dht_i2c.py" <<'PY'
# Placeholder for I2C temperature/humidity sensor (SHT31/DHT20 etc.)
def init(i2c):
    # implement with adafruit library when available
    return None
def read(sensor):
    return None, None
PY

# actuators/__init__.py
cat > "${BASE}/actuators/__init__.py" <<'PY'
# actuators package
PY

# actuators/buzzer.py
cat > "${BASE}/actuators/buzzer.py" <<'PY'
import pwmio, board, time
class Buzzer:
    def __init__(self, pin_num=20, default_freq=440):
        self._pin = getattr(board, f"GP{pin_num}")
        self._pwm = None
        self._freq = default_freq
    def init(self):
        try:
            self._pwm = pwmio.PWMOut(self._pin, frequency=self._freq, duty_cycle=0)
            return True
        except Exception as e:
            print("Buzzer init failed:", e); self._pwm=None; return False
    def tone(self, freq, duration_ms=200, duty=32768):
        if not self._pwm: return
        try:
            self._pwm.frequency = int(freq)
            self._pwm.duty_cycle = int(duty)
            time.sleep(duration_ms/1000.0)
        finally:
            self._pwm.duty_cycle = 0
    def deinit(self):
        try:
            if self._pwm: self._pwm.deinit()
        except Exception: pass
PY

# actuators/ir_tx.py (safe stub)
cat > "${BASE}/actuators/ir_tx.py" <<'PY'
# ir_tx safe stub
import time, board
try:
    import pwmio
except Exception:
    pwmio = None
class NECTransmitter:
    def __init__(self, pin=None, freq=38000, simulate=True):
        self._pin = pin if pin is not None else getattr(board, "GP15")
        self._freq = freq
        self._pwm = None
        self._simulate = simulate
    def init(self):
        if pwmio is None:
            return False
        try:
            self._pwm = pwmio.PWMOut(self._pin, frequency=self._freq, duty_cycle=0)
            return True
        except Exception:
            self._pwm = None
            return False
    def send(self, code, repeats=1):
        if isinstance(code, str):
            code = int(code, 16)
        if self._pwm is None:
            print("ir_tx: simulate send 0x%08X" % code)
            return
        # real send omitted for brevity
    def deinit(self):
        try:
            if self._pwm: self._pwm.deinit()
        except Exception: pass
PY

# ir_rx.py (placeholder lazy init)
cat > "${BASE}/ir_rx.py" <<'PY'
# ir_rx placeholder (use the full version when available)
def init(pin_num=17):
    print("ir_rx: init placeholder")
def deinit():
    print("ir_rx: deinit placeholder")
def read_code(timeout_ms=1200):
    return None
PY

# Make script executable
chmod +x "${BASE}/make_project.sh"
echo "Project skeleton created. Files written to ${BASE}."
