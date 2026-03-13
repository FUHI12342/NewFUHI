# diag_scan.py
# Diagnostic scan mode for Pico 2 W CircuitPython
# Used to detect physical wiring of sensors and modules

import time
import board
import digitalio
import analogio
import busio
import gc

def get_pin(name):
    """Safely get a pin from board module, return None if not found"""
    try:
        return getattr(board, name, None)
    except:
        return None

def scan_i2c_bus(scl_pin, sda_pin, bus_name):
    """Attempt to scan a specific I2C bus pair"""
    scl = get_pin(scl_pin)
    sda = get_pin(sda_pin)
    
    if not scl or not sda:
        return None
        
    try:
        # Check if pins are already in use
        i2c = busio.I2C(scl, sda)
        print(f"[I2C] Scanning {bus_name} (SCL={scl_pin}, SDA={sda_pin})...")
        if i2c.try_lock():
            addresses = i2c.scan()
            i2c.unlock()
            if addresses:
                addr_str = ", ".join([hex(a) for a in addresses])
                print(f"  ✓ Found devices at: {addr_str}")
            else:
                print(f"  (No devices found on {bus_name})")
            return i2c
    except Exception as e:
        # Only print skip if it's a real 'busy' or 'in use' error
        err_msg = str(e).lower()
        if "in use" in err_msg or "busy" in err_msg:
            print(f"[I2C] Skip {bus_name}: pins in use or busy")
        return None

def run():
    print("=" * 60)
    print("  DIAGNOSTIC SCAN MODE ACTIVATED")
    print("  (Press Ctrl+C to exit and return to normal mode)")
    print("=" * 60)

    # 1. Setup Analog Pins
    print("\n[Analog] Monitoring GP26, GP27, GP28 (A0, A1, A2)...")
    analog_pins = {}
    for p_name in ["GP26", "GP27", "GP28"]:
        p_obj = get_pin(p_name)
        if p_obj:
            try:
                analog_pins[p_name] = analogio.AnalogIn(p_obj)
            except Exception as e:
                print(f"  ⚠ Could not monitor analog {p_name}: {e}")

    # 2. Setup Digital Pins for scanning
    # Candidates based on typical Grove/Shield ports
    # Including 6 and 7 (I2C1) as candidates too
    digital_pin_candidates = [0, 1, 4, 5, 6, 7, 14, 15, 16, 18, 20, 21, 22]
    
    # Special handling for LED/GP25
    led_pin = get_pin("LED") or get_pin("GP25")
    
    digital_inputs = {}
    last_digital_states = {}

    print(f"[Digital] Monitoring pins for changes: {digital_pin_candidates}")
    for p_num in digital_pin_candidates:
        p_name = f"GP{p_num}"
        p_obj = get_pin(p_name)
        if p_obj:
            try:
                dio = digitalio.DigitalInOut(p_obj)
                dio.direction = digitalio.Direction.INPUT
                dio.pull = digitalio.Pull.UP
                digital_inputs[p_num] = dio
                last_digital_states[p_num] = dio.value
            except Exception as e:
                # Silently skip if pin is used elsewhere (e.g. by I2C)
                pass
    
    # 3. I2C Bus Discovery
    # We'll try common bus pairs and keep the first successful ones for periodic scanning
    active_i2c_buses = []
    
    # Try I2C0 (GP4/GP5)
    bus0 = scan_i2c_bus("GP5", "GP4", "I2C0")
    if bus0: active_i2c_buses.append(bus0)
    
    # Try I2C1 (GP6/GP7) - common on many Pico 2 setups
    bus1 = scan_i2c_bus("GP7", "GP6", "I2C1")
    if bus1: active_i2c_buses.append(bus1)

    # 4. IR Activity Detection
    ir_candidates = [p for p in [14, 15, 16, 18] if p in digital_inputs]
    print(f"[IR] Monitoring activity on pins: {ir_candidates}")

    # Loop state
    last_analog_print = 0
    i2c_scan_interval = 5.0
    last_i2c_scan = time.monotonic()

    try:
        while True:
            now = time.monotonic()
            
            # --- Analog Scan ---
            if now - last_analog_print > 1.0:
                if analog_pins:
                    a_str = " | ".join([f"{k}: {p.value:5d}" for k, p in analog_pins.items()])
                    print(f"ADC -> {a_str}")
                last_analog_print = now

            # --- Digital Scan (Edge Detect) ---
            for p_num, dio in digital_inputs.items():
                current_val = dio.value
                if current_val != last_digital_states[p_num]:
                    state_str = "HIGH" if current_val else "LOW (ACTIVE)"
                    print(f"[GPIO {p_num:02d}] Transition -> {state_str}")
                    last_digital_states[p_num] = current_val
                    time.sleep(0.01)

            # --- IR Pulse Activity Check ---
            for p_num in ir_candidates:
                dio = digital_inputs[p_num]
                toggle_count = 0
                test_end = time.monotonic() + 0.05
                orig_val = dio.value
                while time.monotonic() < test_end:
                    if dio.value != orig_val:
                        toggle_count += 1
                        orig_val = not orig_val
                
                if toggle_count > 10:
                    print(f"[IR Signal] Activity on GP{p_num}! (Pulses: ~{toggle_count})")

            # --- Periodic Multiple I2C Scan ---
            if now - last_i2c_scan > i2c_scan_interval:
                for i, bus in enumerate(active_i2c_buses):
                    try:
                        if bus.try_lock():
                            addresses = bus.scan()
                            bus.unlock()
                            if addresses:
                                addr_str = ", ".join([hex(a) for a in addresses])
                                print(f"[I2C Bus {i}] Devices active: {addr_str}")
                    except:
                        pass
                last_i2c_scan = now

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nExiting Diagnostic Mode...")
    finally:
        # Cleanup
        for dio in digital_inputs.values():
            try: dio.deinit()
            except: pass
        for p in analog_pins.values():
            try: p.deinit()
            except: pass
        for bus in active_i2c_buses:
            try: bus.deinit()
            except: pass
        gc.collect()

if __name__ == "__main__":
    run()
