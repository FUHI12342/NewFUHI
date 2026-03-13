# sensors/dht_i2c.py
"""I2C温湿度センサー（SHT31/DHT20）ラッパー

I2Cバス経由でSHT31またはDHT20センサーから温度・湿度を読み取る。
code.pyのセンサーデータ（temp/hum）をDjangoに送信するために使用。
"""

import time

# サポートするセンサーのI2Cアドレス
SHT31_ADDR = 0x44
DHT20_ADDR = 0x38


class DHTSensor:
    """I2C温湿度センサークラス（MQ9/Sound等と同じインターフェース）"""

    def __init__(self, i2c_sda_pin=4, i2c_scl_pin=5):
        self._i2c = None
        self._sensor_addr = None
        self._sensor_type = None
        self._sda_pin = i2c_sda_pin
        self._scl_pin = i2c_scl_pin
        self._last_temp = None
        self._last_hum = None

    def init(self):
        """I2Cバスを初期化し、接続されたセンサーを自動検出する"""
        try:
            import board
            import busio

            sda = getattr(board, f"GP{self._sda_pin}")
            scl = getattr(board, f"GP{self._scl_pin}")
            self._i2c = busio.I2C(scl, sda)

            # I2Cバスのロック取得を試行
            retries = 3
            while not self._i2c.try_lock() and retries > 0:
                time.sleep(0.01)
                retries -= 1

            if retries <= 0:
                print("[DHT] I2C bus lock failed")
                return False

            try:
                # SHT31を先に検出
                try:
                    self._i2c.writeto(SHT31_ADDR, bytes([0xF3, 0x2D]))  # ソフトリセット
                    time.sleep(0.01)
                    self._sensor_addr = SHT31_ADDR
                    self._sensor_type = "SHT31"
                    print("[DHT] SHT31 sensor detected and initialized")
                    return True
                except Exception:
                    pass

                # DHT20を検出
                try:
                    self._i2c.writeto(DHT20_ADDR, bytes([0x71]))  # ステータスレジスタ
                    time.sleep(0.01)
                    self._sensor_addr = DHT20_ADDR
                    self._sensor_type = "DHT20"
                    print("[DHT] DHT20 sensor detected and initialized")
                    return True
                except Exception:
                    pass

            finally:
                self._i2c.unlock()

            print("[DHT] No supported I2C temperature/humidity sensor found")
            return False

        except Exception as e:
            print(f"[DHT] Init error: {e}")
            self._i2c = None
            return False

    def read(self):
        """温度と湿度を読み取り、辞書で返す

        Returns:
            dict: {"temp": float|None, "hum": float|None}
        """
        if self._i2c is None or self._sensor_addr is None:
            return {"temp": None, "hum": None}

        try:
            # I2Cバスのロック取得
            if not self._i2c.try_lock():
                return {"temp": self._last_temp, "hum": self._last_hum}

            try:
                temp, hum = self._read_raw()
                if temp is not None:
                    self._last_temp = temp
                    self._last_hum = hum
                return {"temp": self._last_temp, "hum": self._last_hum}
            finally:
                self._i2c.unlock()

        except Exception as e:
            print(f"[DHT] Read error: {e}")
            return {"temp": self._last_temp, "hum": self._last_hum}

    def _read_raw(self):
        """センサーから生データを読み取って変換する"""
        try:
            if self._sensor_type == "SHT31":
                # SHT31 高精度測定コマンド
                self._i2c.writeto(self._sensor_addr, bytes([0x24, 0x00]))
                time.sleep(0.5)

                result = bytearray(6)
                self._i2c.readfrom_into(self._sensor_addr, result)

                temp_raw = (result[0] << 8) | result[1]
                hum_raw = (result[3] << 8) | result[4]

                temperature = -45 + (175 * temp_raw / 65535.0)
                humidity = 100 * hum_raw / 65535.0

                return round(temperature, 1), round(humidity, 1)

            elif self._sensor_type == "DHT20":
                # DHT20 測定トリガー
                self._i2c.writeto(self._sensor_addr, bytes([0xAC, 0x33, 0x00]))
                time.sleep(0.08)

                result = bytearray(7)
                self._i2c.readfrom_into(self._sensor_addr, result)

                hum_raw = (result[1] << 12) | (result[2] << 4) | (result[3] >> 4)
                temp_raw = ((result[3] & 0x0F) << 16) | (result[4] << 8) | result[5]

                humidity = hum_raw * 100 / 1048576.0
                temperature = temp_raw * 200 / 1048576.0 - 50

                return round(temperature, 1), round(humidity, 1)

        except Exception as e:
            print(f"[DHT] Raw read error: {e}")

        return None, None

    def deinit(self):
        """リソース解放"""
        try:
            if self._i2c:
                try:
                    self._i2c.deinit()
                except Exception:
                    pass
        finally:
            self._i2c = None
            self._sensor_addr = None
            self._sensor_type = None

    def self_test(self, samples=3, delay_s=1.0):
        """簡易セルフテスト"""
        result = {"ok": False, "reads": [], "summary": None, "error": None}
        try:
            if not self.init():
                result["error"] = "init_failed"
                return result

            reads = []
            for _ in range(int(samples)):
                v = self.read()
                reads.append(v)
                time.sleep(float(delay_s))

            result["reads"] = reads
            valid_temps = [r["temp"] for r in reads if r.get("temp") is not None]

            if not valid_temps:
                result["summary"] = "no_data"
                result["ok"] = False
            else:
                result["summary"] = f"ok ({self._sensor_type})"
                result["ok"] = True

        except Exception as e:
            result["error"] = str(e)
            result["ok"] = False
        finally:
            try:
                self.deinit()
            except Exception:
                pass

        return result
