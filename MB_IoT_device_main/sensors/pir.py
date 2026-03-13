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
