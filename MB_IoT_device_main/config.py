# config.py (final / fixed)

# ===== Wi-Fi =====
# Load credentials from secrets.py (never commit secrets.py to git)
try:
    from secrets import secrets
    WIFI_SSID = secrets.get('ssid', '')
    WIFI_PASSWORD = secrets.get('password', '')
except ImportError:
    WIFI_SSID = ''
    WIFI_PASSWORD = ''

# ===== Provisioning / button =====
BUTTON_HOLD_SECONDS = 5
PROVISIONING_TIMEOUT = 0      # 起動時の長押しプロビは無効化
BUTTON_ACTIVE_HIGH = False    # Groveボタンは「押したら LOW」なので False
PROVISION_BUTTON_GP = None    # 長押し専用ピンを分けたい時だけ

# ===== Device identity =====
DEVICE_ID = "Ace1"

# MQTT client ids
CLIENT_ID = f"{DEVICE_ID}_sub"
MQTT_CLIENT_ID = CLIENT_ID
PUB_CLIENT_ID = f"{DEVICE_ID}_pub"

# ===== Certs (AWS IoT X.509) =====
CERT_DIR = "certs"
CERT_FILE  = "certs/device-rsa.crt"
KEY_FILE   = "certs/device-private-rsa.pem"
ROOT_CA_FILE = "certs/AmazonRootCA1.pem"
CA_AT_ROOT = False

# ===== AWS IoT =====
AWS_ENDPOINT = "a1c5a3evair1px-ats.iot.ap-northeast-1.amazonaws.com"
AWS_REGION = "ap-northeast-1"

# ===== MQTT Topics =====
TOPIC_BASE = f"devices/{DEVICE_ID}"
TOPIC_SUBSCRIBE = f"{TOPIC_BASE}/cmd/#"
TOPIC_STATUS = f"{TOPIC_BASE}/status"
TOPIC_SENSOR = f"{TOPIC_BASE}/sensors"

# ===== Sensor / timing =====
SENSOR_READ_INTERVAL = 3        # 3秒ごとにアナログ読み取り
MQTT_PUBLISH_INTERVAL = 20      # 30秒ごとにAWS MQTTへ送信
DJANGO_EVENT_INTERVAL = 20      # 30秒ごとにDjangoへ送信
DEDUP_WINDOW = 2                # Django重複送信防止ウィンドウ（秒）

# ===== GPIO mapping =====
A0_GP = 26        # MQ-9
A1_GP = 27        # 照度
A2_GP = 28        # サウンド
BUTTON_GP = 16    # ボタン
BUZZER_GP = 20    # パッシブブザー
PIR_GP = 17       # 人感センサ
I2C_SDA_GP = 4
I2C_SCL_GP = 5
LED_GP = 25

# ===== LCD =====
LCD_TYPE = "char"   # "char" or "oled"

# ===== IR =====
IR_PIN = 15
IR_CARRIER_FREQ = 38000
IR_RX_PIN = 14

# ===== Debug / mode =====
DEBUG = True
LOG_LEVEL = "INFO"
AUTO_INIT = True

# ===== Power / reconnect =====
SLEEP_ENABLED = False
SLEEP_SECONDS = 60
MQTT_RECONNECT_DELAY = 5
MQTT_CONNECT_RETRIES = 5
MQTT_CONNECT_RETRY_DELAY = 2
MAX_RECONNECT_ATTEMPTS = 0

# ===== Aliases =====
AWS_IOT_ENDPOINT = AWS_ENDPOINT
CERT_PATH = CERT_FILE
KEY_PATH = KEY_FILE
ROOT_CA = ROOT_CA_FILE

# ===== Django integration (IoTEvent用) =====
# 注意: HTTPS必須。サーバー側でTLS証明書の設定が必要です。
# 開発用（ローカルMac）- TLS/SSLが設定済みであること
DJANGO_EVENTS_URL = "https://192.168.10.102:8000/api/iot/events/"
# 本番用（AWS EC2）- 現地デプロイ時にこちらに切り替え:
# DJANGO_EVENTS_URL = "https://timebaibai.com/api/iot/events/"
try:
    DJANGO_API_KEY = secrets.get('api_key', '')
except NameError:
    DJANGO_API_KEY = ''