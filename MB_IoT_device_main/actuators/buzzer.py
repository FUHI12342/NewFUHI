# actuators/buzzer.py
# CircuitPython-compatible passive buzzer driver for PWM pins
# Tested on Adafruit CircuitPython 10.x (RP2350/Pico 2 W)
import time
import pwmio
import board

class Buzzer:
    def __init__(self, pin_num, default_freq=880, volume=0.5):
        """
        pin_num: int (e.g., 20) or a board pin object (e.g., board.GP20)
        default_freq: default frequency in Hz for beep()
        volume: 0.0 ~ 1.0 (maps to duty_cycle 0 ~ 65535)
        """
        if isinstance(pin_num, int):
            self.pin = getattr(board, f"GP{pin_num}")
        else:
            self.pin = pin_num

        self.default_freq = int(default_freq)
        self.volume = max(0.0, min(1.0, float(volume)))
        self.pwm = None

    def init(self):
        """
        Lazy-initializes PWM on first use. Call is optional.
        """
        try:
            if self.pwm is None:
                # duty_cycle=0 keeps the buzzer silent until tone() sets it
                self.pwm = pwmio.PWMOut(self.pin, frequency=self.default_freq, duty_cycle=0)
            return True
        except Exception as e:
            print("Buzzer init error:", e)
            self.pwm = None
            return False

    def _ensure_pwm(self, freq):
        """
        Ensure PWM object exists and is set to target frequency.
        Recreate it if changing frequency fails (some ports require reinit).
        """
        freq = int(freq)
        try:
            if self.pwm is None:
                self.pwm = pwmio.PWMOut(self.pin, frequency=freq, duty_cycle=0)
            else:
                try:
                    self.pwm.frequency = freq
                except Exception:
                    # Re-create PWM when frequency update fails
                    self.pwm.deinit()
                    self.pwm = pwmio.PWMOut(self.pin, frequency=freq, duty_cycle=0)
            return True
        except Exception as e:
            print("Buzzer tone error: PWM init failed", e)
            self.pwm = None
            return False

    def set_volume(self, volume):
        """
        Set volume 0.0 ~ 1.0 (linear mapping to duty_cycle).
        """
        self.volume = max(0.0, min(1.0, float(volume)))

    def _duty_from_volume(self):
        # 16-bit duty (0..65535). 50% ≈ 32768
        return int(65535 * self.volume)

    def tone(self, frequency, duration_ms):
        """
        Play a tone at frequency (Hz) for duration_ms (milliseconds).
        Returns True on success, False on failure.
        """
        try:
            freq = int(frequency)
            dur = int(duration_ms)
        except Exception:
            print("Buzzer tone error: invalid frequency/duration")
            return False

        if freq <= 0 or dur <= 0:
            print("Buzzer tone error: frequency/duration invalid")
            return False

        if not self._ensure_pwm(freq):
            return False

        try:
            self.pwm.duty_cycle = self._duty_from_volume()
            time.sleep(dur / 1000.0)
            self.pwm.duty_cycle = 0
            return True
        except Exception as e:
            print("Buzzer tone error: playback failed", e)
            return False

    def beep(self, duration_ms=150):
        """
        Quick beep using default frequency.
        """
        return self.tone(self.default_freq, duration_ms)

    def play_sequence(self, notes):
        """
        Play a sequence of notes: [(freq_hz, dur_ms), ...]
        """
        ok = True
        for f, d in notes:
            ok = self.tone(f, d) and ok
            time.sleep(0.03)
        return ok

    def silence(self):
        """
        Immediately silence the buzzer without deinitializing PWM.
        """
        if self.pwm:
            try:
                self.pwm.duty_cycle = 0
            except Exception:
                pass

    def deinit(self):
        """
        Release PWM resources.
        """
        if self.pwm:
            try:
                self.pwm.deinit()
            except Exception:
                pass
            self.pwm = None

    def is_initialized(self):
        return self.pwm is not None