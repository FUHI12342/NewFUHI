# sensors/button.py
import time
import digitalio
import board

def _get_pin(pin_num: int):
    name = "GP{}".format(pin_num)
    return getattr(board, name)

class Button:
    def __init__(self, pin_num: int, active_low: bool = True, debounce_ms: int = 50):
        self.pin_num = pin_num
        self.active_low = active_low
        self.debounce_s = (debounce_ms or 50) / 1000.0

        self._dio = None
        self._stable_pressed = False
        self._last_raw_pressed = False
        self._last_change_t = 0.0
        self._fell_latched = False

    def init(self) -> bool:
        pin = _get_pin(self.pin_num)
        self._dio = digitalio.DigitalInOut(pin)
        self._dio.switch_to_input(pull=digitalio.Pull.UP)  # active-low前提
        raw = self._raw_pressed()
        self._stable_pressed = raw
        self._last_raw_pressed = raw
        self._last_change_t = time.monotonic()
        self._fell_latched = False
        return True

    def deinit(self) -> None:
        if self._dio:
            try:
                self._dio.deinit()
            except:
                pass
        self._dio = None

    def _raw_pressed(self) -> bool:
        if not self._dio:
            return False
        v = bool(self._dio.value)
        return (not v) if self.active_low else v

    def _update(self) -> None:
        now = time.monotonic()
        raw = self._raw_pressed()

        if raw != self._last_raw_pressed:
            self._last_raw_pressed = raw
            self._last_change_t = now

        if (now - self._last_change_t) >= self.debounce_s:
            if raw != self._stable_pressed:
                if (not self._stable_pressed) and raw:
                    self._fell_latched = True
                self._stable_pressed = raw

    def read(self) -> bool:
        self._update()
        return bool(self._stable_pressed)

    def is_pressed(self) -> bool:
        """Alias for backward compatibility"""
        return self.read()

    @property
    def pressed(self) -> bool:
        """Property alias for read()"""
        return self.read()

    def fell(self) -> bool:
        self._update()
        if self._fell_latched:
            self._fell_latched = False
            return True
        return False