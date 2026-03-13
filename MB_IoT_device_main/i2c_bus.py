# i2c_bus.py
# Centralized I2C bus management with TCA9548A multiplexer support
# Provides fallback for mux-less operation

import time
import board
import busio

# TCA9548A I2C Multiplexer
TCA9548A_ADDR = 0x70

# Global I2C instances
_i2c_bus = None
_tca_mux = None
_mux_available = False

def _init_i2c_bus():
    """Initialize the main I2C bus (I2C1: GP6 SDA, GP7 SCL)"""
    global _i2c_bus
    if _i2c_bus is None:
        try:
            # Use I2C1 as configured in main.py
            _i2c_bus = busio.I2C(board.GP7, board.GP6)
            print("I2C bus initialized (SDA=GP6, SCL=GP7)")
        except Exception as e:
            print("I2C bus init failed:", e)
            _i2c_bus = None
    return _i2c_bus

def _init_tca_mux():
    """Initialize TCA9548A multiplexer if present"""
    global _tca_mux, _mux_available
    if _tca_mux is not None:
        return _tca_mux

    bus = _init_i2c_bus()
    if bus is None:
        return None

    try:
        # Check if TCA9548A is present
        bus.writeto(TCA9548A_ADDR, bytes([0x00]))  # Select no channels
        _mux_available = True
        _tca_mux = TCA9548A_ADDR
        print("TCA9548A multiplexer detected at 0x70")
    except Exception:
        _mux_available = False
        _tca_mux = None
        print("TCA9548A multiplexer not detected, operating in direct mode")

    return _tca_mux

def get_i2c():
    """Get the main I2C bus instance"""
    return _init_i2c_bus()

def get_tca_mux():
    """Get the TCA9548A multiplexer address if available"""
    _init_tca_mux()
    return _tca_mux if _mux_available else None

def select_channel(channel):
    """
    Select I2C multiplexer channel (0-7)
    If no mux, this is a no-op (direct connection)
    """
    if not _mux_available:
        return True  # No mux, always "selected"

    if channel < 0 or channel > 7:
        print("Invalid channel:", channel)
        return False

    bus = get_i2c()
    if bus is None:
        return False

    try:
        # TCA9548A channel select: write channel mask
        bus.writeto(TCA9548A_ADDR, bytes([1 << channel]))
        return True
    except Exception as e:
        print("Channel select failed:", e)
        return False

def scan_i2c_bus(channel=None):
    """
    Scan I2C bus for devices
    If channel specified, select that mux channel first
    Returns list of addresses found
    """
    if channel is not None:
        if not select_channel(channel):
            return []

    bus = get_i2c()
    if bus is None:
        return []

    addresses = []
    for addr in range(0x08, 0x78):  # Standard I2C address range
        try:
            bus.writeto(addr, bytes([]))  # Quick write to test presence
            addresses.append(addr)
        except Exception:
            pass

    return addresses

def is_mux_available():
    """Check if TCA9548A multiplexer is available"""
    _init_tca_mux()
    return _mux_available

# Initialize on import
_init_i2c_bus()
_init_tca_mux()