# sensors/mq9.py
"""MQ9 ガスセンサ（AnalogIn）ラッパー"""
import analogio
import board
import time

class MQ9:
    def __init__(self, pin_num=26):
        try:
            if isinstance(pin_num, int):
                self._pin = getattr(board, f"GP{pin_num}")
            else:
                self._pin = pin_num
        except Exception:
            self._pin = getattr(board, "GP26")
        self._adc = None

    def init(self):
        try:
            self._adc = analogio.AnalogIn(self._pin)
            return True
        except Exception as e:
            print("MQ9 init failed:", e)
            self._adc = None
            return False

    def read(self):
        try:
            if not self._adc:
                return None
            return int(self._adc.value)
        except Exception as e:
            print("MQ9 read error:", e)
            return None

    def deinit(self):
        try:
            if self._adc:
                try:
                    self._adc.deinit()
                except Exception:
                    pass
        finally:
            self._adc = None

    def self_test(self, samples=5, delay_s=0.1):
        """
        簡易セルフテスト:
        - init() を試みる
        - samples 回 read() を行い値の有無と変動を確認
        - 結果を dict で返す
        """
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
            valid_reads = [r for r in reads if r is not None]
            if not valid_reads:
                result["summary"] = "no_data"
                result["ok"] = False
            else:
                # 値の変動があるか（簡易判定）
                if max(valid_reads) != min(valid_reads):
                    result["summary"] = "ok_variation"
                else:
                    result["summary"] = "ok_constant"
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