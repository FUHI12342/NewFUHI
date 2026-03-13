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
