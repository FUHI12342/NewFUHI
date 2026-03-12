# ir_tx.py
# NEC IR transmitter helper (safe when hardware absent)
import time
import board

try:
    import pwmio
except Exception:
    pwmio = None  # ハードウェア用モジュールが無ければ None にする

class NECTransmitter:
    """
    NEC 赤外線送信器（安全版）
    - init(pin=..., freq=38000) で遅延初期化可能
    - deinit() でリソース解放
    - send(code, repeats=1) で NEC 送信（code は int または "0x..." 文字列）
    - ハードが無い場合は例外を投げずログ出力のみ行う
    """
    def __init__(self, pin=None, freq=38000, simulate_if_no_hw=True):
        """
        pin: board.GPxx オブジェクト もしくは整数ピン番号（例: 15）
        freq: キャリア周波数（Hz）
        simulate_if_no_hw: ハードが無い場合に擬似送信ログを出すか
        """
        self._freq = int(freq)
        self._pwm = None
        self._pin_spec = pin if pin is not None else getattr(board, "GP15")
        self._simulate = bool(simulate_if_no_hw)
        self._available = False
        # 初期化は遅延（init()）するが、コンストラクタで自動初期化したい場合は init() を呼ぶ
        try:
            # もし pin が数値なら board.GP{n} に変換を試みる
            if isinstance(self._pin_spec, int):
                self._pin_spec = getattr(board, f"GP{int(self._pin_spec)}")
        except Exception:
            # 変換失敗してもそのまま進める（board オブジェクトであることを期待）
            pass

    def init(self):
        """PWMOut を初期化する。失敗しても例外を投げない（_available を False にする）"""
        if self._available:
            return True
        if pwmio is None:
            if self._simulate:
                print("ir_tx: pwmio not available, running in simulate mode")
                self._available = False
                return False
            else:
                raise RuntimeError("pwmio module not available")
        try:
            self._pwm = pwmio.PWMOut(self._pin_spec, frequency=self._freq, duty_cycle=0)
            self._available = True
            return True
        except Exception as e:
            # ハードが無い、またはピンが使用中などの理由で初期化失敗
            print("ir_tx: PWM init failed:", e)
            self._pwm = None
            self._available = False
            return False

    def deinit(self):
        """PWMOut を解放する"""
        try:
            if self._pwm is not None:
                try:
                    self._pwm.duty_cycle = 0
                except Exception:
                    pass
                try:
                    self._pwm.deinit()
                except Exception:
                    pass
            self._pwm = None
        finally:
            self._available = False

    def _carrier_on(self):
        """キャリアをオンにする（ハードが無ければ noop）"""
        if self._available and self._pwm is not None:
            try:
                self._pwm.duty_cycle = 32768  # 50%
            except Exception:
                pass

    def _carrier_off(self):
        """キャリアをオフにする（ハードが無ければ noop）"""
        if self._available and self._pwm is not None:
            try:
                self._pwm.duty_cycle = 0
            except Exception:
                pass

    def is_available(self):
        """ハードウェアが利用可能かを返す"""
        return bool(self._available)

    def send(self, code, repeats=1, verbose=True):
        """
        NEC フォーマット送信
        - code: int または "0x20DF10EF" のような文字列
        - repeats: 送信回数
        - verbose: True のときログを出力
        """
        # code を int に変換
        try:
            if isinstance(code, str):
                code = int(code, 16)
            code = int(code)
        except Exception as e:
            raise ValueError("Invalid code format: %s" % code) from e

        # 初期化されていなければ試みる（失敗しても擬似動作にフォールバック）
        if not self._available:
            self.init()

        # 送信ロジック（タイミングは秒単位の sleep）
        for r in range(int(repeats)):
            if self._available:
                # Leader
                self._carrier_on(); time.sleep(0.009)   # 9000us
                self._carrier_off(); time.sleep(0.0045) # 4500us

                # 32bit LSB first
                for i in range(32):
                    bit = (code >> i) & 1
                    self._carrier_on(); time.sleep(0.000562)  # mark 562us
                    self._carrier_off()
                    if bit:
                        time.sleep(0.001687)  # space for 1
                    else:
                        time.sleep(0.000562)  # space for 0

                # Stop bit
                self._carrier_on(); time.sleep(0.000562)
                self._carrier_off()
                time.sleep(0.1)
            else:
                # ハードが無い場合は擬似送信（ログのみ）
                if verbose:
                    print("ir_tx: simulate send NEC 0x%08X (repeats=%d)" % (code, r+1))
                # 実際のタイミングを模して短く待つ（負荷軽減）
                time.sleep(0.02)

        if verbose:
            print("ir_tx: send complete 0x%08X repeats=%d (hw=%s)" % (code, repeats, self._available))

    def send_raw(self, pulses, verbose=True):
        """
        RAW パルス列を送信する（Daikin AC 等の非NEC対応）
        - pulses: [mark_us, space_us, mark_us, space_us, ...] マイクロ秒単位のリスト
        - verbose: True のときログを出力
        """
        if not pulses:
            if verbose:
                print("ir_tx: send_raw called with empty pulses")
            return

        # 初期化されていなければ試みる
        if not self._available:
            self.init()

        if verbose:
            print("ir_tx: send_raw %d pulses (hw=%s)" % (len(pulses), self._available))

        if self._available:
            for i, duration_us in enumerate(pulses):
                if i % 2 == 0:
                    # Even index = mark (carrier on)
                    self._carrier_on()
                else:
                    # Odd index = space (carrier off)
                    self._carrier_off()
                # Convert microseconds to seconds for sleep
                time.sleep(duration_us / 1_000_000)
            # Ensure carrier is off at end
            self._carrier_off()
        else:
            # Simulate mode
            if verbose:
                print("ir_tx: simulate send_raw %d pulses" % len(pulses))
            time.sleep(0.02)

        if verbose:
            print("ir_tx: send_raw complete %d pulses (hw=%s)" % (len(pulses), self._available))

# 簡易テスト（ハードが無くても安全）
if __name__ == "__main__":
    tx = NECTransmitter(pin=getattr(board, "GP15"), freq=38000, simulate_if_no_hw=True)
    print("ir_tx: starting self-test (no hardware required)")
    tx.send("0x20DF10EF", repeats=1)
    tx.deinit()