# diagnostics.py
# Comprehensive hardware diagnostics for Pico 2 W CircuitPython
# Tests all sensors, actuators, WiFi, and reports results

import time
import gc
import json
import wifi
import socketpool
import microcontroller

# Diagnostic result status constants
STATUS_PASS = "PASS"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"


class DiagnosticResult:
    """Stores the result of a single diagnostic test"""
    
    def __init__(self, test_name, status, message="", metadata=None):
        self.test_name = test_name
        self.status = status  # PASS, WARN, or FAIL
        self.message = message
        self.metadata = metadata or {}
        self.timestamp = time.monotonic()
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        result = {
            "status": self.status,
        }
        if self.message:
            result["note"] = self.message
        if self.metadata:
            result.update(self.metadata)
        return result


class DiagnosticsRunner:
    """Main diagnostics coordinator"""
    
    def __init__(self, secrets):
        self.secrets = secrets
        self.results = {}
        self.wifi_info = {}
        self.device_id = secrets.get("device", "pico2w_unknown")
        self.start_time = time.monotonic()
        
        # LCD reference (will be initialized if available)
        self.lcd = None
        
    def log(self, msg):
        """Print log message"""
        print(f"[DIAG] {msg}")
    
    def lcd_print(self, line1, line2=""):
        """Print to LCD if available"""
        if self.lcd:
            try:
                self.lcd.clear()
                self.lcd.set_cursor(0, 0)
                self.lcd.print(line1[:16])
                if line2:
                    self.lcd.set_cursor(0, 1)
                    self.lcd.print(line2[:16])
            except Exception as e:
                self.log(f"LCD print error: {e}")
    
    def validate_config(self):
        """Validate secrets.py configuration and detect dummy values"""
        self.log("Validating configuration...")
        
        api_key = self.secrets.get("api_key", "")
        server_base = self.secrets.get("server_base", "")
        ssid = self.secrets.get("ssid", "")
        password = self.secrets.get("password", "")
        
        # Check for dummy/placeholder values
        dummy_api_keys = ["YOUR_API_KEY_HERE", "REPLACE_ME", "dummy", "test", "example"]
        dummy_servers = ["your-server.com", "example.com", "localhost", "https://your-server.com"]
        
        errors = []
        
        if not api_key or api_key in dummy_api_keys:
            errors.append("api_key is missing or contains placeholder value")
        
        if not server_base or server_base in dummy_servers:
            errors.append("server_base is missing or contains placeholder value")
        
        if not ssid:
            errors.append("WiFi ssid is missing")
        
        if not password:
            errors.append("WiFi password is missing")
        
        if errors:
            return DiagnosticResult(
                "config_validation",
                STATUS_FAIL,
                "Invalid or dummy configuration detected: " + "; ".join(errors)
            )
        
        self.log("✓ Configuration valid")
        return DiagnosticResult("config_validation", STATUS_PASS, "All required fields present")
    
    def test_wifi_autoconnect(self):
        """Test WiFi auto-connect with retry logic"""
        self.log("=" * 50)
        self.log("Testing WiFi Auto-Connect")
        self.log("=" * 50)
        
        self.lcd_print("WiFi Test", "Connecting...")
        
        ssid = self.secrets.get("ssid", "")
        password = self.secrets.get("password", "")
        
        max_retries = 3
        timeout_per_attempt = 10  # seconds
        
        for attempt in range(1, max_retries + 1):
            self.log(f"Connection attempt {attempt}/{max_retries}")
            
            try:
                # Check if already connected
                if wifi.radio.connected:
                    self.log("Already connected, disconnecting first...")
                    wifi.radio.enabled = False
                    time.sleep(0.5)
                    wifi.radio.enabled = True
                    time.sleep(0.5)
                
                # Attempt connection
                wifi.radio.connect(ssid, password, timeout=timeout_per_attempt)
                
                if wifi.radio.connected:
                    # Connection successful!
                    ip = str(wifi.radio.ipv4_address)
                    rssi = wifi.radio.ap_info.rssi
                    
                    self.log(f"✓ WiFi connected!")
                    self.log(f"  SSID: {ssid}")
                    self.log(f"  IP: {ip}")
                    self.log(f"  RSSI: {rssi} dBm")
                    
                    self.lcd_print("WiFi: PASS", f"IP:{ip[:13]}")
                    
                    # Test DNS resolution
                    dns_ok = False
                    try:
                        server_host = self.secrets.get("server_base", "").replace("https://", "").replace("http://", "")
                        if server_host:
                            pool = socketpool.SocketPool(wifi.radio)
                            addr_info = pool.getaddrinfo(server_host, 443)
                            if addr_info:
                                dns_ip = addr_info[0][4][0]
                                self.log(f"✓ DNS resolution OK: {server_host} -> {dns_ip}")
                                dns_ok = True
                    except Exception as e:
                        self.log(f"⚠ DNS resolution failed: {e}")
                    
                    # Store WiFi info
                    self.wifi_info = {
                        "status": STATUS_PASS,
                        "ip": ip,
                        "rssi": rssi,
                        "dns_ok": dns_ok,
                        "attempts": attempt
                    }
                    
                    return DiagnosticResult(
                        "wifi_autoconnect",
                        STATUS_PASS,
                        f"Connected on attempt {attempt}",
                        {"ip": ip, "rssi": rssi, "dns_ok": dns_ok}
                    )
                    
            except Exception as e:
                self.log(f"Attempt {attempt} failed: {e}")
                time.sleep(2)  # Wait before retry
        
        # All retries exhausted
        self.log("✗ WiFi connection failed after all retries")
        self.lcd_print("WiFi: FAIL", "Check config")
        
        self.wifi_info = {
            "status": STATUS_FAIL,
            "error": "Connection failed after retries"
        }
        
        return DiagnosticResult(
            "wifi_autoconnect",
            STATUS_FAIL,
            f"Failed to connect after {max_retries} attempts"
        )
    
    def test_lcd_display(self):
        """Test LCD display initialization and output"""
        self.log("=" * 50)
        self.log("Testing LCD Display")
        self.log("=" * 50)
        
        try:
            import busio
            import board
            from lcd_display import LCD
            
            # Try common I2C addresses
            addresses_to_try = [0x27, 0x3F]
            
            for addr in addresses_to_try:
                try:
                    self.log(f"Trying LCD at I2C address 0x{addr:02X}...")
                    
                    # Initialize I2C
                    i2c = busio.I2C(board.GP5, board.GP4)
                    self.lcd = LCD(i2c, addr)
                    
                    # Test display
                    self.lcd.clear()
                    self.lcd.set_cursor(0, 0)
                    self.lcd.print("DIAGNOSTIC MODE")
                    self.lcd.set_cursor(0, 1)
                    self.lcd.print("LCD: PASS")
                    
                    self.log(f"✓ LCD initialized at 0x{addr:02X}")
                    
                    return DiagnosticResult(
                        "lcd_display",
                        STATUS_PASS,
                        f"Initialized at I2C address 0x{addr:02X}",
                        {"i2c_address": f"0x{addr:02X}"}
                    )
                    
                except Exception as e:
                    self.log(f"Address 0x{addr:02X} failed: {e}")
                    continue
            
            # None of the addresses worked
            self.log("✗ LCD initialization failed at all addresses")
            return DiagnosticResult(
                "lcd_display",
                STATUS_FAIL,
                "I2C initialization failed - check wiring/address"
            )
            
        except Exception as e:
            self.log(f"✗ LCD test error: {e}")
            return DiagnosticResult("lcd_display", STATUS_FAIL, str(e))
    
    def test_button(self):
        """Test button with user interaction (timeout)"""
        self.log("=" * 50)
        self.log("Testing Button (GPIO5)")
        self.log("=" * 50)
        
        self.lcd_print("Button Test", "Press in 10s...")
        
        try:
            import board
            import digitalio
            
            button = digitalio.DigitalInOut(board.GP5)
            button.direction = digitalio.Direction.INPUT
            button.pull = digitalio.Pull.UP
            
            self.log("Waiting for button press (10 seconds)...")
            timeout = 10
            start = time.monotonic()
            pressed = False
            
            while (time.monotonic() - start) < timeout:
                if not button.value:  # Active LOW
                    pressed = True
                    self.log("✓ Button press detected!")
                    self.lcd_print("Button: PASS", "Detected!")
                    time.sleep(0.5)
                    break
                time.sleep(0.05)
            
            button.deinit()
            
            if pressed:
                return DiagnosticResult("button", STATUS_PASS, "Button press detected")
            else:
                self.log("⚠ Button press timeout")
                self.lcd_print("Button: WARN", "No press")
                return DiagnosticResult("button", STATUS_WARN, "No press detected in 10s - check wiring")
                
        except Exception as e:
            self.log(f"✗ Button test error: {e}")
            return DiagnosticResult("button", STATUS_FAIL, str(e))
    
    def test_mq9_sensor(self):
        """Test MQ-9 gas sensor (electrical validation)"""
        self.log("=" * 50)
        self.log("Testing MQ-9 Gas Sensor")
        self.log("=" * 50)
        
        self.lcd_print("MQ-9 Test", "Reading...")
        
        try:
            import board
            import analogio
            
            adc = analogio.AnalogIn(board.GP26)
            
            # Read multiple samples
            samples = []
            for i in range(10):
                samples.append(adc.value)
                time.sleep(0.1)
            
            adc.deinit()
            
            # Calculate statistics
            avg = sum(samples) / len(samples)
            min_val = min(samples)
            max_val = max(samples)
            variance = sum((x - avg) ** 2 for x in samples) / len(samples)
            std_dev = variance ** 0.5
            
            self.log(f"MQ-9 readings: avg={avg:.0f}, min={min_val}, max={max_val}, std={std_dev:.1f}")
            
            # Check if stuck at rails
            if avg < 100 or avg > 65400:
                self.log("✗ MQ-9 value stuck at rail")
                self.lcd_print("MQ-9: FAIL", "Stuck value")
                return DiagnosticResult(
                    "mq9",
                    STATUS_FAIL,
                    "Sensor reading stuck (possible wiring issue)",
                    {"avg_value": int(avg)}
                )
            
            self.log("✓ MQ-9 sensor responding")
            self.lcd_print("MQ-9: PASS", f"Avg:{int(avg)}")
            
            return DiagnosticResult(
                "mq9",
                STATUS_PASS,
                "Sensor electrically active",
                {"avg_value": int(avg), "std_dev": round(std_dev, 1)}
            )
            
        except Exception as e:
            self.log(f"✗ MQ-9 test error: {e}")
            return DiagnosticResult("mq9", STATUS_FAIL, str(e))
    
    def test_pir_sensor(self):
        """Test PIR motion sensor (user interaction)"""
        self.log("=" * 50)
        self.log("Testing PIR Motion Sensor")
        self.log("=" * 50)
        
        self.lcd_print("PIR Test", "Move in 10s...")
        
        try:
            import board
            import digitalio
            
            pir = digitalio.DigitalInOut(board.GP22)
            pir.direction = digitalio.Direction.INPUT
            
            self.log("Waiting for motion detection (10 seconds)...")
            timeout = 10
            start = time.monotonic()
            detected = False
            
            while (time.monotonic() - start) < timeout:
                if pir.value:  # HIGH when motion detected
                    detected = True
                    self.log("✓ Motion detected!")
                    self.lcd_print("PIR: PASS", "Motion detected")
                    time.sleep(0.5)
                    break
                time.sleep(0.1)
            
            pir.deinit()
            
            if detected:
                return DiagnosticResult("pir", STATUS_PASS, "Motion detected")
            else:
                self.log("⚠ PIR timeout - no motion detected")
                self.lcd_print("PIR: WARN", "No motion")
                return DiagnosticResult("pir", STATUS_WARN, "No motion in 10s - check sensor or move in front")
                
        except Exception as e:
            self.log(f"✗ PIR test error: {e}")
            return DiagnosticResult("pir", STATUS_FAIL, str(e))
    
    def test_light_sensor(self):
        """Test light sensor with variation detection"""
        self.log("=" * 50)
        self.log("Testing Light Sensor")
        self.log("=" * 50)
        
        self.lcd_print("Light Test", "Cover/uncover...")
        
        try:
            import board
            import analogio
            
            adc = analogio.AnalogIn(board.GP27)
            
            self.log("Sampling light levels for 10 seconds...")
            self.log("Please cover and uncover the sensor...")
            
            samples = []
            timeout = 10
            start = time.monotonic()
            
            while (time.monotonic() - start) < timeout:
                samples.append(adc.value)
                time.sleep(0.2)
            
            adc.deinit()
            
            # Calculate variation
            min_val = min(samples)
            max_val = max(samples)
            range_val = max_val - min_val
            avg_val = sum(samples) / len(samples)
            variation_pct = (range_val / 65535) * 100
            
            self.log(f"Light sensor: min={min_val}, max={max_val}, range={range_val}, variation={variation_pct:.1f}%")
            
            if variation_pct > 10:  # More than 10% variation
                self.log("✓ Light sensor responding to changes")
                self.lcd_print("Light: PASS", f"Var:{variation_pct:.0f}%")
                return DiagnosticResult(
                    "light",
                    STATUS_PASS,
                    "Sensor responding to light changes",
                    {"variation_percent": round(variation_pct, 1), "avg_value": int(avg_val)}
                )
            else:
                self.log("⚠ Light sensor shows little variation")
                self.lcd_print("Light: WARN", "Low variation")
                return DiagnosticResult(
                    "light",
                    STATUS_WARN,
                    f"Low variation ({variation_pct:.1f}%) - ensure sensor exposed and cover/uncover",
                    {"variation_percent": round(variation_pct, 1)}
                )
                
        except Exception as e:
            self.log(f"✗ Light sensor test error: {e}")
            return DiagnosticResult("light", STATUS_FAIL, str(e))
    
    def test_buzzer(self):
        """Test buzzer beep"""
        self.log("=" * 50)
        self.log("Testing Buzzer")
        self.log("=" * 50)
        
        self.lcd_print("Buzzer Test", "Listen...")
        
        try:
            import board
            import pwmio
            
            buzzer = pwmio.PWMOut(board.GP20, frequency=1000, duty_cycle=0, variable_frequency=True)
            
            # Beep 3 times
            for i in range(3):
                self.log(f"Beep {i+1}/3")
                buzzer.duty_cycle = 32768  # 50%
                time.sleep(0.2)
                buzzer.duty_cycle = 0
                time.sleep(0.2)
            
            buzzer.deinit()
            
            self.log("✓ Buzzer test complete")
            self.lcd_print("Buzzer: PASS", "Heard beeps?")
            time.sleep(2)
            
            return DiagnosticResult("buzzer", STATUS_PASS, "3 beeps generated (user confirm audible)")
            
        except Exception as e:
            self.log(f"✗ Buzzer test error: {e}")
            return DiagnosticResult("buzzer", STATUS_FAIL, str(e))
    
    def test_speaker(self):
        """Test speaker/audio output"""
        self.log("=" * 50)
        self.log("Testing Speaker")
        self.log("=" * 50)
        
        self.lcd_print("Speaker Test", "Listen...")
        
        try:
            import board
            import pwmio
            
            # Use PWM for tone generation
            speaker = pwmio.PWMOut(board.GP18, frequency=440, duty_cycle=0, variable_frequency=True)
            
            # Play two tones
            tones = [440, 880]  # A4, A5
            for freq in tones:
                self.log(f"Playing {freq}Hz...")
                speaker.frequency = freq
                speaker.duty_cycle = 32768  # 50%
                time.sleep(0.3)
                speaker.duty_cycle = 0
                time.sleep(0.1)
            
            speaker.deinit()
            
            self.log("✓ Speaker test complete")
            self.lcd_print("Speaker: PASS", "Heard tones?")
            time.sleep(2)
            
            return DiagnosticResult("speaker", STATUS_PASS, "Tones generated (user confirm audible)")
            
        except Exception as e:
            self.log(f"✗ Speaker test error: {e}")
            return DiagnosticResult("speaker", STATUS_FAIL, str(e))
    
    def test_temp_humidity(self):
        """Test temperature/humidity sensor"""
        self.log("=" * 50)
        self.log("Testing Temperature/Humidity Sensor")
        self.log("=" * 50)
        
        self.lcd_print("Temp/Hum Test", "Reading...")
        
        try:
            import board
            import busio
            from sensors.dht_i2c import DHTSensor
            
            i2c = busio.I2C(board.GP5, board.GP4)
            sensor = DHTSensor(i2c)
            
            # Try reading
            temp_c, humidity = sensor.read()
            
            if temp_c is None or humidity is None:
                self.log("✗ Sensor returned None values")
                self.lcd_print("DHT: FAIL", "No reading")
                return DiagnosticResult("temp_humidity", STATUS_FAIL, "Sensor not responding")
            
            # Check reasonable ranges
            if not (-20 <= temp_c <= 60):
                self.log(f"⚠ Temperature out of range: {temp_c}°C")
                return DiagnosticResult(
                    "temp_humidity",
                    STATUS_WARN,
                    f"Temperature out of expected range: {temp_c}°C",
                    {"temperature_c": temp_c, "humidity_percent": humidity}
                )
            
            if not (0 <= humidity <= 100):
                self.log(f"⚠ Humidity out of range: {humidity}%")
                return DiagnosticResult(
                    "temp_humidity",
                    STATUS_WARN,
                    f"Humidity out of expected range: {humidity}%",
                    {"temperature_c": temp_c, "humidity_percent": humidity}
                )
            
            self.log(f"✓ Temperature: {temp_c}°C, Humidity: {humidity}%")
            self.lcd_print("DHT: PASS", f"T:{temp_c}C H:{humidity}%")
            
            return DiagnosticResult(
                "temp_humidity",
                STATUS_PASS,
                "Sensor reading in valid range",
                {"temperature_c": temp_c, "humidity_percent": humidity}
            )
            
        except Exception as e:
            self.log(f"✗ DHT test error: {e}")
            return DiagnosticResult("temp_humidity", STATUS_FAIL, str(e))
    
    def test_ir_loopback(self):
        """Test IR TX/RX with loopback (TX and RX must be positioned facing each other)"""
        self.log("=" * 50)
        self.log("Testing IR TX/RX Loopback")
        self.log("=" * 50)
        
        self.lcd_print("IR Test", "TX->RX...")
        
        try:
            import board
            from ir_tx import NECTransmitter
            from ir_receiver import IRReceiver
            
            # Initialize TX
            tx = NECTransmitter(board.GP14)
            self.log("IR TX initialized on GP14")
            
            # Initialize RX
            rx = IRReceiver(board.GP15)
            self.log("IR RX initialized on GP15")
            
            # Send test pattern
            test_code = 0x20DF10EF  # LG TV power code (common test pattern)
            self.log(f"Transmitting NEC code: 0x{test_code:08X}")
            
            for i in range(3):
                tx.transmit(test_code)
                self.log(f"  Sent {i+1}/3")
                time.sleep(0.5)
            
            # Listen for signals
            self.log("Listening for IR signals (3 seconds)...")
            timeout = 3
            start = time.monotonic()
            signal_detected = False
            
            while (time.monotonic() - start) < timeout:
                frame = rx.read()
                if frame:
                    signal_detected = True
                    self.log(f"✓ IR signal received: {frame}")
                    break
                time.sleep(0.1)
            
            # Cleanup
            tx.deinit()
            rx.deinit()
            
            if signal_detected:
                self.log("✓ IR loopback successful")
                self.lcd_print("IR: PASS", "Loopback OK")
                return DiagnosticResult("ir_loopback", STATUS_PASS, "TX->RX communication verified")
            else:
                self.log("⚠ No IR signal received")
                self.lcd_print("IR: WARN", "No signal")
                return DiagnosticResult(
                    "ir_loopback",
                    STATUS_WARN,
                    "No signal detected - check TX/RX positioning (should face each other, ~5-10cm apart)"
                )
                
        except Exception as e:
            self.log(f"✗ IR test error: {e}")
            return DiagnosticResult("ir_loopback", STATUS_FAIL, str(e))
    
    def generate_report(self):
        """Generate diagnostic report as dictionary"""
        # Calculate ISO timestamp (approximate - CircuitPython doesn't have full datetime)
        elapsed = time.monotonic() - self.start_time
        
        report = {
            "device": self.device_id,
            "timestamp": f"{time.monotonic():.0f}s_since_boot",  # Basic timestamp
            "elapsed_seconds": round(elapsed, 1),
            "wifi": self.wifi_info,
            "tests": {}
        }
        
        # Add all test results
        for test_name, result in self.results.items():
            report["tests"][test_name] = result.to_dict()
        
        return report
    
    def save_report_to_file(self, filename="/diag_report.json"):
        """Save diagnostic report to file"""
        try:
            report = self.generate_report()
            with open(filename, "w") as f:
                json.dump(report, f)
            self.log(f"✓ Report saved to {filename}")
            return True
        except Exception as e:
            self.log(f"✗ Failed to save report: {e}")
            return False
    
    def send_report_to_server(self):
        """Send diagnostic report to Django API (non-blocking)"""
        if self.wifi_info.get("status") != STATUS_PASS:
            self.log("⚠ Skipping server upload - WiFi not connected")
            return False
        
        try:
            self.log("Sending diagnostic report to Django API...")
            
            from pico_device.django_api import DjangoAPIClient
            
            api = DjangoAPIClient(
                server_url=self.secrets.get("server_base"),
                api_key=self.secrets.get("api_key"),
                device_id=self.device_id
            )
            
            # Send as an event
            report = self.generate_report()
            payload = {
                "type": "diagnostic_report",
                "payload": report
            }
            
            response = api.send_device_status(payload)
            
            if response:
                self.log("✓ Diagnostic report uploaded to server")
                return True
            else:
                self.log("⚠ Server upload failed (no response)")
                return False
                
        except Exception as e:
            self.log(f"⚠ Server upload error (non-critical): {e}")
            return False
    
    def run_all_tests(self):
        """Run all diagnostic tests in sequence"""
        self.log("")
        self.log("=" * 60)
        self.log("  PICO 2W COMPREHENSIVE DIAGNOSTICS")
        self.log("  Device: " + self.device_id)
        self.log("=" * 60)
        self.log("")
        
        # 1. Configuration validation
        result = self.validate_config()
        self.results["config_validation"] = result
        if result.status == STATUS_FAIL:
            self.log("⚠ Configuration invalid - continuing other tests but WiFi will fail")
        
        # 2. LCD (initialize early so we can use it for other tests)
        self.results["lcd_display"] = self.test_lcd_display()
        time.sleep(2)
        
        # 3. WiFi auto-connect
        self.results["wifi_autoconnect"] = self.test_wifi_autoconnect()
        time.sleep(2)
        
        # 4. Hardware tests (order: simple to complex)
        self.results["button"] = self.test_button()
        time.sleep(1)
        
        self.results["buzzer"] = self.test_buzzer()
        time.sleep(1)
        
        self.results["speaker"] = self.test_speaker()
        time.sleep(1)
        
        self.results["mq9"] = self.test_mq9_sensor()
        time.sleep(1)
        
        self.results["light"] = self.test_light_sensor()
        time.sleep(1)
        
        self.results["pir"] = self.test_pir_sensor()
        time.sleep(1)
        
        self.results["temp_humidity"] = self.test_temp_humidity()
        time.sleep(1)
        
        self.results["ir_loopback"] = self.test_ir_loopback()
        time.sleep(1)
        
        # Summary
        self.log("")
        self.log("=" * 60)
        self.log("  DIAGNOSTICS COMPLETE")
        self.log("=" * 60)
        
        # Count results
        pass_count = sum(1 for r in self.results.values() if r.status == STATUS_PASS)
        warn_count = sum(1 for r in self.results.values() if r.status == STATUS_WARN)
        fail_count = sum(1 for r in self.results.values() if r.status == STATUS_FAIL)
        
        self.log(f"Results: {pass_count} PASS, {warn_count} WARN, {fail_count} FAIL")
        self.log("")
        
        # Detailed results
        for test_name, result in self.results.items():
            status_symbol = "✓" if result.status == STATUS_PASS else ("⚠" if result.status == STATUS_WARN else "✗")
            self.log(f"{status_symbol} {test_name}: {result.status} - {result.message}")
        
        self.log("")
        
        # Save report
        self.lcd_print("Saving report", "Please wait...")
        self.save_report_to_file()
        
        # Try to upload (non-blocking)
        self.lcd_print("Uploading...", "")
        self.send_report_to_server()
        
        # Final LCD message
        self.lcd_print("Diagnostics Done", f"P:{pass_count} W:{warn_count} F:{fail_count}")
        
        self.log("=" * 60)
        self.log("Diagnostic report saved to /diag_report.json")
        self.log("Set DIAGNOSTIC_MODE=False in secrets.py to return to normal mode")
        self.log("=" * 60)


def run_full_diagnostics(secrets):
    """Entry point for running full diagnostics"""
    runner = DiagnosticsRunner(secrets)
    runner.run_all_tests()
    
    # Free memory
    gc.collect()


if __name__ == "__main__":
    # For standalone testing
    try:
        import secrets as secrets_mod
        secrets = getattr(secrets_mod, "secrets", {})
    except ImportError:
        print("ERROR: secrets.py not found")
        secrets = {}
    
    run_full_diagnostics(secrets)
