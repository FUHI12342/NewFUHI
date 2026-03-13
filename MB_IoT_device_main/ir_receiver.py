# ir_receiver.py
# Enhanced IR receiver with NEC protocol decode and RAW pulse capture
import time
import board
import digitalio
import array

class IRReceiver:
    """
    IR Receiver with NEC protocol decode and RAW pulse capture
    Supports:
    - NEC protocol decode (32-bit address+command)
    - RAW pulse capture for unknown protocols
    - Timeout-based reading with non-blocking support
    """
    
    # NEC timing constants (in microseconds)
    NEC_HEADER_MARK = 9000
    NEC_HEADER_SPACE = 4500
    NEC_BIT_MARK = 562
    NEC_ONE_SPACE = 1687
    NEC_ZERO_SPACE = 562
    NEC_RPT_SPACE = 2250
    
    TOLERANCE = 0.3  # 30% tolerance for timing
    
    def __init__(self, pin_num=17, debug=False):
        """
        pin_num: GPIO pin number (e.g., 17 for GP17)
        debug: enable debug logging
        """
        self.pin_num = pin_num
        self.debug = debug
        self.pin = None
        self.initialized = False
    
    def log(self, msg):
        if self.debug:
            print(f"[IR_RX] {msg}")
    
    def init(self):
        """Initialize IR receiver pin"""
        if self.initialized:
            return True
        
        try:
            pin_obj = getattr(board, f"GP{self.pin_num}")
            self.pin = digitalio.DigitalInOut(pin_obj)
            self.pin.direction = digitalio.Direction.INPUT
            # IR receivers typically output HIGH when idle, LOW when receiving
            self.initialized = True
            self.log(f"IR receiver initialized on GP{self.pin_num}")
            return True
        except Exception as e:
            self.log(f"Failed to initialize IR receiver: {e}")
            return False
    
    def deinit(self):
        """Deinitialize IR receiver"""
        try:
            if self.pin:
                self.pin.deinit()
            self.pin = None
            self.initialized = False
            self.log("IR receiver deinitialized")
        except Exception as e:
            self.log(f"Deinit error: {e}")
    
    def _wait_for_edge(self, target_value, timeout_us):
        """
        Wait for pin to reach target_value (True/False)
        Returns elapsed time in microseconds, or None if timeout
        """
        start = time.monotonic_ns()
        timeout_ns = timeout_us * 1000
        
        while (time.monotonic_ns() - start) < timeout_ns:
            if self.pin.value == target_value:
                return (time.monotonic_ns() - start) // 1000  # return us
        
        return None
    
    def _in_range(self, value, target, tolerance=None):
        """Check if value is within tolerance of target"""
        if tolerance is None:
            tolerance = self.TOLERANCE
        lower = target * (1 - tolerance)
        upper = target * (1 + tolerance)
        return lower <= value <= upper
    
    def read_raw_pulses(self, max_pulses=200, timeout_ms=1000):
        """
        Read raw IR pulses (microseconds of HIGH and LOW periods)
        Returns list of pulse durations (alternating SPACE, MARK, SPACE, ...)
        or None if timeout/error
        """
        if not self.initialized:
            if not self.init():
                return None
        
        pulses = []
        timeout_ns = timeout_ms * 1_000_000
        start = time.monotonic_ns()
        
        try:
            # Wait for signal to go LOW (start of transmission)
            while self.pin.value and (time.monotonic_ns() - start) < timeout_ns:
                pass
            
            if (time.monotonic_ns() - start) >= timeout_ns:
                return None  # No signal detected
            
            # Capture alternating edges
            current_state = False  # Started LOW
            edge_time = time.monotonic_ns()
            
            for _ in range(max_pulses):
                # Wait for edge
                target_state = not current_state
                while self.pin.value == current_state:
                    if (time.monotonic_ns() - start) >= timeout_ns:
                        # Timeout, return what we have
                        return pulses if len(pulses) > 0 else None
                
                # Record pulse duration
                now = time.monotonic_ns()
                duration_us = (now - edge_time) // 1000
                pulses.append(duration_us)
                
                edge_time = now
                current_state = target_state
            
            return pulses
        except Exception as e:
            self.log(f"Raw pulse read error: {e}")
            return None
    
    def decode_nec(self, pulses):
        """
        Decode NEC protocol from raw pulses
        Returns dict with:
        {
            "protocol": "NEC",
            "address": int,
            "command": int,
            "code": int (full 32-bit),
            "bits": 32
        }
        or None if not NEC or decode failed
        """
        if not pulses or len(pulses) < 67:  # NEC needs at least 67 edges
            return None
        
        idx = 0
        
        # Check header: MARK (9ms) + SPACE (4.5ms)
        if not self._in_range(pulses[idx], self.NEC_HEADER_MARK):
            return None
        idx += 1
        
        if not self._in_range(pulses[idx], self.NEC_HEADER_SPACE):
            # Check for repeat code (2.25ms space)
            if self._in_range(pulses[idx], self.NEC_RPT_SPACE):
                return {"protocol": "NEC_REPEAT"}
            return None
        idx += 1
        
        # Read 32 bits
        code = 0
        for bit_num in range(32):
            # Mark (should be ~562us)
            if idx >= len(pulses):
                return None
            if not self._in_range(pulses[idx], self.NEC_BIT_MARK, tolerance=0.4):
                return None
            idx += 1
            
            # Space (determines bit value)
            if idx >= len(pulses):
                return None
            
            if self._in_range(pulses[idx], self.NEC_ONE_SPACE):
                code |= (1 << bit_num)
            elif self._in_range(pulses[idx], self.NEC_ZERO_SPACE):
                pass  # bit is 0
            else:
                return None  # Invalid timing
            idx += 1
        
        # Extract address and command (NEC sends LSB first)
        address = code & 0xFF
        address_inv = (code >> 8) & 0xFF
        command = (code >> 16) & 0xFF
        command_inv = (code >> 24) & 0xFF
        
        # Validate inverse bytes (should be ~address and ~command)
        # Some devices don't follow this strictly, so we log but don't fail
        if (address ^ address_inv) != 0xFF:
            self.log(f"Warning: NEC address inverse mismatch")
        if (command ^ command_inv) != 0xFF:
            self.log(f"Warning: NEC command inverse mismatch")
        
        return {
            "protocol": "NEC",
            "address": address,
            "command": command,
            "code": code,
            "bits": 32
        }
    
    def read_code(self, timeout_ms=1200, return_raw=True):
        """
        Read and decode IR code
        Returns dict with decoded data or None if no signal
        
        If NEC decode succeeds:
        {
            "protocol": "NEC",
            "address": int,
            "command": int,
            "code": int,
            "bits": 32,
            "raw": [...] (if return_raw=True)
        }
        
        If NEC decode fails but pulses captured:
        {
            "protocol": "RAW",
            "raw": [list of pulse durations],
            "pulse_count": int
        }
        """
        pulses = self.read_raw_pulses(timeout_ms=timeout_ms)
        
        if not pulses:
            return None
        
        # Try NEC decode first
        nec_result = self.decode_nec(pulses)
        
        if nec_result:
            if return_raw:
                nec_result["raw"] = pulses
            self.log(f"NEC decoded: addr={nec_result.get('address', '?'):#x}, cmd={nec_result.get('command', '?'):#x}")
            return nec_result
        
        # If NEC decode failed, return raw pulses
        self.log(f"Unknown protocol, returning raw pulses (count={len(pulses)})")
        return {
            "protocol": "RAW",
            "raw": pulses,
            "pulse_count": len(pulses)
        }

# Global instance for easy import (lazy init)
_receiver = None

def init(pin_num=17, debug=False):
    """Initialize global IR receiver instance"""
    global _receiver
    _receiver = IRReceiver(pin_num=pin_num, debug=debug)
    return _receiver.init()

def deinit():
    """Deinitialize global IR receiver"""
    global _receiver
    if _receiver:
        _receiver.deinit()
        _receiver = None

def read_code(timeout_ms=1200):
    """Read code using global instance (auto-init if needed)"""
    global _receiver
    if _receiver is None:
        _receiver = IRReceiver(pin_num=17, debug=False)
        _receiver.init()
    
    return _receiver.read_code(timeout_ms=timeout_ms)
