# lcd_display.py
# Grove - LCD RGB Backlight (テキストLCD部分) 用の簡易ドライバ
# I2Cアドレス:
#   テキスト表示: 0x3E
#   RGBバックライト: 0x62（ここでは未使用）

import time

# I2C ハンドルと状態
_i2c = None
_cols = 16
_rows = 2
display_type = None  # "grove_char" など

DISPLAY_TEXT_ADDR = 0x3E  # LCD テキスト部

# ------------------------
# 内部ヘルパ
# ------------------------

def _i2c_write(addr, buf):
    """ロック付きで I2C 書き込み"""
    global _i2c
    if _i2c is None:
        return
    t0 = time.monotonic()
    # ロック取得（最大1秒くらい粘る）
    while not _i2c.try_lock():
        if time.monotonic() - t0 > 1.0:
            print("I2C lock timeout")
            return
        time.sleep(0.01)
    try:
        _i2c.writeto(addr, buf)
    except Exception as e:
        print("I2C write error:", e)
    finally:
        try:
            _i2c.unlock()
        except Exception:
            pass


def _cmd(cmd):
    """LCD へのコマンド送信"""
    _i2c_write(DISPLAY_TEXT_ADDR, bytes([0x80, cmd & 0xFF]))


def _data(byte):
    """LCD へのデータ送信（1文字）"""
    _i2c_write(DISPLAY_TEXT_ADDR, bytes([0x40, byte & 0xFF]))


def _clear_display():
    """LCD 全消去"""
    _cmd(0x01)  # clear display
    time.sleep(0.05)


def _init_lcd_core():
    """テキストLCDの基本初期化"""
    # ディスプレイ ON、カーソルOFF、ブリンクOFF など
    _cmd(0x0C)  # display on, cursor off
    _cmd(0x28)  # 2行モード, 5x8ドット
    time.sleep(0.05)


def _set_text_raw(text):
    """テキスト全体を表示（最大2行）"""
    global _cols, _rows
    _clear_display()
    _init_lcd_core()

    col = 0
    row = 0
    for ch in str(text):
        if ch == "\n" or col >= _cols:
            col = 0
            row += 1
            if row >= _rows:
                break
            # 2行目の先頭へ移動 (0xC0)
            _cmd(0xC0)
            if ch == "\n":
                continue
        _data(ord(ch))
        col += 1


# ------------------------
# 外向け API
# ------------------------

def init_grove_lcd(channel=None, cols=16, rows=2):
    """
    Grove RGB LCD テキスト部を初期化。
    channel: TCA9548A channel (None for direct connection)
    """
    import i2c_bus

    global _i2c, _cols, _rows, display_type

    # Select mux channel if specified
    if channel is not None:
        if not i2c_bus.select_channel(channel):
            print("LCD: Failed to select mux channel", channel)
            display_type = None
            return

    _i2c = i2c_bus.get_i2c()
    if _i2c is None:
        print("LCD: I2C bus not available")
        display_type = None
        return

    _cols = cols
    _rows = rows
    display_type = "grove_char"

    try:
        print("Init Grove LCD (addr=0x3E)")
        _clear_display()
        _init_lcd_core()
        _set_text_raw("LCD Ready")
        print("Grove LCD initialized.")
    except Exception as e:
        print("Grove LCD init error:", e)
        display_type = None


def show_text(message):
    """1行〜2行テキストを表示。\\n で改行。"""
    if _i2c is None:
        print("LCD fallback show_text:", message)
        return
    try:
        _set_text_raw(str(message))
    except Exception as e:
        print("show_text error:", e)


def show_text_lines(*lines):
    """
    最大2行まで表示。
    lines[0] → 1行目, lines[1] → 2行目
    """
    if _i2c is None:
        print("LCD fallback show_text_lines:")
        for l in lines:
            print("  ", l)
        return

    try:
        # 2行まで詰めて \\n で繋ぐ
        text_lines = []
        for i in range(2):
            if i < len(lines):
                text_lines.append(str(lines[i]))
        text = "\n".join(text_lines)
        _set_text_raw(text)
    except Exception as e:
        print("show_text_lines error:", e)


def show_sensors(sensors):
    """
    センサー値をざっくり2行で表示。
    1行目: MQ9 / Light
    2行目: Sound / Temp / Hum（入る範囲で）
    """
    if sensors is None:
        print("LCD fallback show_sensors: None")
        return

    mq9 = sensors.get("mq9", "-")
    light = sensors.get("light", "-")
    sound = sensors.get("sound", "-")
    temp = sensors.get("temp", "-")
    hum = sensors.get("hum", "-")

    line1 = f"MQ9:{mq9} L:{light}"
    line2 = f"S:{sound} T:{temp} H:{hum}"
    show_text_lines(line1, line2)


def show_time_and_sensors(time_str, mq9, light, sound, temp, hum):
    """
    時刻＋センサー要約を表示。
    1行目: HH:MM MQ9:xxx
    2行目: L:xx S:xx
    """
    mq9_s = "-" if mq9 is None else str(mq9)
    light_s = "-" if light is None else str(light)
    sound_s = "-" if sound is None else str(sound)
    temp_s = "-" if temp is None else str(temp)
    hum_s = "-" if hum is None else str(hum)

    line1 = f"{time_str} MQ9:{mq9_s}"
    # 16文字に収める
    line1 = line1[:16]

    line2 = f"L:{light_s} S:{sound_s}"
    line2 = line2[:16]

    show_text_lines(line1, line2)


def show_provisioning_info(ssid, ip, password_hint):
    """
    APプロビジョニング情報をLCDに表示（16x2対応）
    2画面を交互表示
    """
    import time

    screen_a = [ssid[:16], ip[:16]]
    screen_b = [f"PW:{password_hint}", "Open browser"]

    start_time = time.monotonic()
    while time.monotonic() - start_time < 300:  # 5分間表示（タイムアウトまで）
        try:
            show_text_lines(screen_a[0], screen_a[1])
            time.sleep(2)
            show_text_lines(screen_b[0], screen_b[1])
            time.sleep(2)
        except Exception:
            break