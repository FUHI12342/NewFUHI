# code.py
# Raspberry Pi Pico 2 W CircuitPython - IoT Main Loop
# Integrated with WiFi Hardening and Setup AP functionality
# BUILD: MB_IoT_device_main 20260126-1400

import time
import gc
import board
import microcontroller
import supervisor

# Disable autoreload (belt-and-suspenders - already done in boot.py)
try:
    supervisor.runtime.autoreload = False
    print("[CODE] AutoReload disabled via supervisor.runtime.autoreload")
except Exception as e:
    print(f"[CODE] Could not set supervisor.runtime.autoreload: {e}")
    # Fallback method
    try:
        supervisor.disable_autoreload()
        print("[CODE] AutoReload disabled via supervisor.disable_autoreload()")
    except Exception as e2:
        print(f"[CODE] Could not call supervisor.disable_autoreload(): {e2}")

# Import WiFi Hardening components
from pico_device import ConfigurationManager, WiFiManager, SetupAPHandler
from pico_device.config_manager import DjangoConfigSource, LocalFileConfigSource, SecretsConfigSource

print("[BUILD] MB_IoT_device_main 20260126-1400")
print("[MAIN] Pico WiFi Hardening initialized...")

# Configuration and secrets
secrets = {}
try:
    from secrets import secrets as secrets_dict
    secrets = secrets_dict
except ImportError:
    try:
        import secrets as secrets_mod
        secrets = getattr(secrets_mod, "secrets", {})
    except ImportError:
        pass

if not secrets:
    print("WARNING: secrets.py not found or empty! Use secrets.py.sample as template.")

# IR modules (Lazy loaded in init_ir)
NECTransmitter = None
ir_receiver = None

# Sensors (Lazy loaded in init_sensors)
MQ9 = None
LightSensor = None
SoundSensor = None
PIR = None
Button = None

# Actuators (Lazy loaded in init_actuators)
Buzzer = None

# ============================
# Configuration
# ============================
DEBUG = True
SENSOR_INTERVAL = 10  # seconds between sensor readings
PIR_INTERVAL = 5  # seconds between PIR status reports (independent of SENSOR_INTERVAL)
IR_CHECK_INTERVAL = 0.2  # seconds between IR checks
MQ9_THRESHOLD = 500  # default, will be updated from server

# Feature Flags
FEATURE_LIGHT = False  # Disable light sensor (not connected)

# Device configuration
DEVICE_ID = secrets.get('device', 'pico2w_001')
WIFI_FAILURE_THRESHOLD = 3
SETUP_CHECK_INTERVAL = 30  # seconds

# IR Learning Mode
BUTTON_HOLD_DURATION = 10  # seconds to enter learning mode
LED_BLINK_INTERVAL = 0.4  # seconds for LED blink during learning

# GPIO Pin mapping - UPDATED for Grove Shield (2026-02-01)
# MQ-9 (CO sensor) -> A0 = GP26
# Sound (Microphone) -> A2 = GP28
# Buzzer (Speaker) -> D20 = GP20
# PIR (Motion) -> D18 = GP18
# Button -> D16 = GP16 (Active Low)
# IR TX -> UART0 TX = GP0
# IR RX -> UART1 RX = GP5
PIN_MQ9 = 26
PIN_LIGHT = 27  # Not connected, kept for compatibility
PIN_SOUND = 28
PIN_PIR = 18  # Changed from 22
PIN_BUZZER = 20
PIN_IR_RX = 5  # Changed from 15 (Grove UART1 RX)
PIN_IR_TX = 0  # Changed from 14 (UART0 TX)
PIN_BUTTON = 16  # Changed from 5 (Active Low)

# Button Debounce
BUTTON_DEBOUNCE_MS = 50

# ============================
# Helper Functions
# ============================
def log(msg):
    if DEBUG:
        print(f"[MAIN] {msg}")

def safe_init(component, name):
    """Safely initialize a component, return True if successful"""
    try:
        result = component.init()
        log(f"{name} initialized: {result}")
        return result
    except Exception as e:
        log(f"{name} initialization error: {e}")
        return False

def safe_parse_threshold(value, default=MQ9_THRESHOLD):
    """Safely parse threshold value from server config
    
    Handles: None, empty string, "500", 0, -1, etc.
    Always returns valid positive int or default.
    """
    try:
        # Handle None or empty string
        if value is None:
            return default
        
        # Convert to string and strip whitespace
        str_val = str(value).strip()
        if str_val == "" or str_val.lower() == "none":
            return default
        
        # Try to parse as int
        parsed = int(float(str_val))  # Handle "500.0" too
        
        # Validate it's positive
        if parsed <= 0:
            log(f"WARNING: Invalid threshold {parsed} (<= 0), using default {default}")
            return default
        
        return parsed
        
    except (ValueError, TypeError) as e:
        log(f"WARNING: Could not parse threshold '{value}': {e}, using default {default}")
        return default

# ============================
# Main Application with WiFi Hardening
# ============================
class IoTDevice:
    def __init__(self):
        self.device_id = DEVICE_ID
        self.api = None
        self.ir_rx = None
        self.ir_tx = None
        self.sensors = {}
        self.actuators = {}
        
        self.last_sensor_time = 0
        self.last_ir_time = 0
        self.last_check_time = 0
        self.button = None
        
        self.mq9_threshold = MQ9_THRESHOLD
        self.running = True
        
        # IR Learning Mode state
        self.learning_mode = False
        self.btn_press_started_at = None
        self.led = None  # Will be initialized if board.LED available
        self.led_last_toggle = 0
        self.led_state = False
        
        # PIR Edge Detection
        self.last_pir = False
        self.last_pir_publish_time = 0
        
        # MQ-9 Alert Control
        self.alert_enabled = True  # Default, updated from server config
        
        # WiFi Hardening components
        self.config_manager = None
        self.wifi_manager = None
        self.setup_handler = None
        
        # Initialize WiFi hardening
        self._init_wifi_hardening()
    
    def _init_wifi_hardening(self):
        """Initialize WiFi hardening components"""
        try:
            # Create configuration sources
            config_sources = [
                DjangoConfigSource(),  # Highest priority
                LocalFileConfigSource(),  # Medium priority  
                SecretsConfigSource()  # Lowest priority
            ]
            
            # Initialize configuration manager
            self.config_manager = ConfigurationManager(
                device_id=self.device_id,
                failure_threshold=WIFI_FAILURE_THRESHOLD,
                config_sources=config_sources
            )
            
            # Initialize WiFi manager
            self.wifi_manager = WiFiManager(
                config_manager=self.config_manager,
                failure_threshold=WIFI_FAILURE_THRESHOLD
            )
            
            # Initialize Setup AP handler
            self.setup_handler = SetupAPHandler(self.device_id)
            
            log("WiFi hardening components initialized")
        except Exception as e:
            log(f"WiFi hardening init error: {e}")
            # Force setup mode if initialization fails
            self._enter_setup_mode("INIT_ERROR")
    
    def _attempt_wifi_connection(self):
        """Attempt WiFi connection with Setup AP fallback"""
        log("Attempting WiFi connection...")
        
        try:
            # Check if we should enter setup mode immediately
            if self.wifi_manager.should_enter_setup_mode():
                reason = self.wifi_manager.setup_reason or "UNKNOWN"
                self._enter_setup_mode(reason)
                return
            
            # Attempt WiFi connection
            success = self.wifi_manager.connect_wifi()
            
            if success:
                log(f"WiFi connected successfully to {self.wifi_manager.get_current_ssid()}")
                self._on_wifi_connected()
            else:
                log("WiFi connection failed")
                
                # Check if we should enter setup mode after failure
                if self.wifi_manager.should_enter_setup_mode():
                    reason = self.wifi_manager.setup_reason or "CONNECTION_FAILED"
                    self._enter_setup_mode(reason)
                
        except Exception as e:
            log(f"WiFi connection error: {e}")
            self._enter_setup_mode("WIFI_ERROR")
    
    def _enter_setup_mode(self, reason: str):
        """Enter Setup AP mode - CRITICAL: Must be reliable"""
        log(f"*** ENTERING SETUP MODE *** Reason: {reason}")
        
        try:
            # Force setup mode in WiFi manager
            self.wifi_manager.force_setup_mode(reason)
            
            # Activate Setup AP
            self.setup_handler.activate_setup_mode()
            
            # Start web server for configuration
            self.setup_handler.serve_web_interface()
            
            # Setup mode loop - stay here until configuration is complete
            self._setup_mode_loop()
            
        except Exception as e:
            log(f"CRITICAL: Setup mode error: {e}")
            # Last resort - restart device
            log("Restarting device...")
            microcontroller.reset()
    
    def _setup_mode_loop(self):
        """Loop while in setup mode"""
        log("Setup mode active - waiting for configuration...")
        
        while True:
            try:
                # Blink LED to indicate setup mode (if available)
                if hasattr(board, 'LED'):
                    import digitalio
                    led = digitalio.DigitalInOut(board.LED)
                    led.direction = digitalio.Direction.OUTPUT
                    led.value = not led.value
                
                time.sleep(0.5)
                
                # Check for configuration updates
                # In real implementation, this would check for web form submissions
                # and call self.setup_handler.handle_config_update()
                
                # For now, just maintain setup mode
                # TODO: Implement web server request handling
                
            except KeyboardInterrupt:
                log("Setup mode interrupted")
                break
            except Exception as e:
                log(f"Setup mode loop error: {e}")
                time.sleep(1)
    
    def _on_wifi_connected(self):
        """Called when WiFi connection is established"""
        try:
            log("WiFi connected - performing post-connection setup")
            
            # Reset failure count
            self.wifi_manager.reset_failure_count()
            
            # Initialize Django API client
            self.init_api()
            
        except Exception as e:
            log(f"Post-connection setup error: {e}")
    
    def init_api(self):
        """Initialize Django API client"""
        log("Initializing Django API client...")
        
        try:
            from django_api import DjangoAPIClient
            
            # Get configuration from config manager
            config = self.config_manager.get_valid_config()
            if config:
                self.api = DjangoAPIClient(
                    server_url=config.server_url,
                    api_key=config.api_key,
                    device_id=self.device_id
                )
                
                # Fetch server config (no save to avoid Errno 30 on read-only FS)
                log("Fetching configuration from server...")
                server_config = self.api.fetch_config(save_to_file=False)
                if server_config:
                    log("✓ Config fetched successfully")
                    # Update threshold if provided - use safe parsing
                    raw_threshold = server_config.get("mq9_threshold")
                    self.mq9_threshold = safe_parse_threshold(raw_threshold, MQ9_THRESHOLD)
                    
                    # Update alert_enabled
                    self.alert_enabled = server_config.get("alert_enabled", True)
                    log(f"  MQ9 threshold: {self.mq9_threshold}, Alert: {self.alert_enabled}")
                else:
                    log("⚠ Config fetch failed, using defaults")
            else:
                log("No valid configuration for API client")
                self.api = None
                
        except ImportError:
            log("ERROR: django_api.py not found! Cannot use server features.")
            self.api = None
        except Exception as e:
            log(f"API initialization error: {e}")
            self.api = None
    
    def init_sensors(self):
        """Initialize all sensors"""
        log("Initializing sensors...")
        
        global MQ9, LightSensor, SoundSensor, PIR, Button
        try:
            from sensors.mq9 import MQ9
            if FEATURE_LIGHT:
                from sensors.light import LightSensor
            from sensors.sound import SoundSensor
            from sensors.pir import PIR
            from sensors.button import Button
        except ImportError as e:
            log(f"WARNING: Some sensor modules missing: {e}")
        
        if MQ9:
            self.sensors["mq9"] = MQ9(pin_num=PIN_MQ9)
        if FEATURE_LIGHT and LightSensor:
            self.sensors["light"] = LightSensor(pin_num=PIN_LIGHT)
        if SoundSensor:
            self.sensors["sound"] = SoundSensor(pin_num=PIN_SOUND)
        if PIR:
            self.sensors["pir"] = PIR(pin_num=PIN_PIR)
        if Button:
            self.button = Button(pin_num=PIN_BUTTON, active_low=True, debounce_ms=BUTTON_DEBOUNCE_MS)
            self.sensors["button"] = self.button
        
        for name, sensor in self.sensors.items():
            safe_init(sensor, name)
    
    def init_actuators(self):
        """Initialize actuators (buzzer, etc.)"""
        log("Initializing actuators...")
        
        global Buzzer
        try:
            from actuators.buzzer import Buzzer
        except ImportError:
            log("Buzzer module not found, skipping.")
            Buzzer = None
            
        if Buzzer:
            self.actuators["buzzer"] = Buzzer(pin_num=PIN_BUZZER)
            safe_init(self.actuators["buzzer"], "buzzer")
            
        # Initialize LED for learning mode (if available)
        try:
            import digitalio
            if hasattr(board, 'LED'):
                self.led = digitalio.DigitalInOut(board.LED)
                self.led.direction = digitalio.Direction.OUTPUT
                self.led.value = False
                log("LED initialized for learning mode")
        except Exception as e:
            log(f"LED init error: {e}")
    
    def init_ir(self):
        """Initialize IR TX/RX"""
        log("Initializing IR modules...")
        
        global ir_receiver, NECTransmitter
        try:
            import ir_receiver as ir_rx_mod
            ir_receiver = ir_rx_mod
            from ir_tx import NECTransmitter as tx_class
            NECTransmitter = tx_class
        except ImportError as e:
            log(f"WARNING: IR modules missing: {e}")
        
        # IR Receiver
        if ir_receiver:
            try:
                self.ir_rx = ir_receiver.IRReceiver(pin_num=PIN_IR_RX, debug=DEBUG)
                safe_init(self.ir_rx, "IR RX")
            except Exception as e:
                log(f"IR RX init error: {e}")
        
        # IR Transmitter
        if NECTransmitter:
            try:
                self.ir_tx = NECTransmitter(pin=PIN_IR_TX, freq=38000, simulate_if_no_hw=True)
                safe_init(self.ir_tx, "IR TX")
            except Exception as e:
                log(f"IR TX init error: {e}")
    
    def read_sensors(self):
        """Read all sensor values"""
        values = {}
        
        for name, sensor in self.sensors.items():
            try:
                values[name] = sensor.read()
            except Exception as e:
                log(f"Error reading {name}: {e}")
                values[name] = None
        
        return values
    
    def check_ir_receiver(self):
        """Check for IR signals and post to Django"""
        if not self.ir_rx:
            return
        
        try:
            ir_data = self.ir_rx.read_code(timeout_ms=100)
            
            if ir_data:
                # If in learning mode, handle registration
                if self.learning_mode:
                    log(f"Learning mode: IR signal received")
                    event_type = "ir_learned"
                    self.led_state = True # Keep LED on during processing
                    if self.led: self.led.value = True
                else:
                    event_type = "ir_rx"
                
                protocol = ir_data.get("protocol", "UNKNOWN")
                log(f"IR RX: protocol={protocol}")
                
                 # Log protocol-specific details
                if protocol == "NEC":
                    log(f"  addr={ir_data.get('address', '?'):#x}, cmd={ir_data.get('command', '?'):#x}, code={ir_data.get('code', '?'):#x}")
                elif protocol == "RAW":
                    raw_len = len(ir_data.get("raw", []))
                    log(f"  raw_pulses={raw_len}")
                
                # Prepare event payload
                event_data = {
                    "event_type": event_type,
                    "payload": {
                        "protocol": protocol,
                        "ts": time.time(),
                    }
                }
                
                # Add protocol-specific fields
                if protocol == "NEC":
                    event_data["payload"]["address"] = ir_data.get("address")
                    event_data["payload"]["command"] = ir_data.get("command")
                    event_data["payload"]["code"] = ir_data.get("code")
                    event_data["payload"]["bits"] = ir_data.get("bits", 32)
                elif protocol == "RAW":
                    # For RAW, send pulse count and first few pulses (don't overflow)
                    raw_pulses = ir_data.get("raw", [])
                    event_data["payload"]["pulse_count"] = len(raw_pulses)
                    event_data["payload"]["raw_sample"] = raw_pulses[:20]  # First 20 pulses
                
                # Post to Django
                if self.api:
                    success, status, info = self.api.post_event(event_data)
                    if success:
                        log(f"  ✓ {event_type} event posted to server")
                        
                        # If learning mode success, exit mode
                        if self.learning_mode:
                            log("IR Learned! Exiting learning mode.")
                            self.learning_mode = False
                            if self.led: self.led.value = False
                            # Success melody
                            if "buzzer" in self.actuators:
                                try:
                                    self.actuators["buzzer"].tone(1500, 200)
                                    time.sleep(0.2)
                                    self.actuators["buzzer"].tone(2000, 400)
                                except: pass
                    else:
                        log(f"  ✗ {event_type} event post failed: {status} ({info})")
                
                # Beep if buzzer available
                if "buzzer" in self.actuators:
                    try:
                        self.actuators["buzzer"].tone(1000, 100)
                    except:
                        pass
        
        except Exception as e:
            log(f"IR check error: {e}")
    
    def send_ir_test(self, code=0x20DF10EF):
        """Send a test IR signal"""
        if not self.ir_tx:
            log("IR TX not available")
            return
        
        try:
            log(f"IR TX: sending code={code:#x}")
            self.ir_tx.send(code, repeats=1, verbose=True)
            log("  ✓ IR TX executed")
            
            # Log TX event to Django
            if self.api:
                event_data = {
                    "event_type": "ir_tx",
                    "payload": {
                        "protocol": "NEC",
                        "code": code,
                        "bits": 32,
                        "ts": time.time()
                    }
                }
                success, status, info = self.api.post_event(event_data)
                if success:
                    log("  ✓ IR TX event posted to server")
                else:
                    log(f"  ✗ IR TX event post failed: {status} ({info})")
        
        except Exception as e:
            log(f"IR TX error: {e}")
    
    def check_button(self):
        """Check for button press and post event to Django"""
        if not self.button:
            return
            
        try:
            # Check for press start/continue for learning mode
            if hasattr(self.button, 'is_pressed') and self.button.is_pressed():
                if self.btn_press_started_at is None:
                    self.btn_press_started_at = time.monotonic()
                
                # Check hold duration
                duration = time.monotonic() - self.btn_press_started_at
                if duration >= BUTTON_HOLD_DURATION and not self.learning_mode:
                    log(f"Button held for {BUTTON_HOLD_DURATION}s -> ENTERING LEARNING MODE")
                    self.learning_mode = True
                    self.btn_press_started_at = None # Reset
                    
                    # Beep to indicate mode entry
                    if "buzzer" in self.actuators:
                        try:
                            self.actuators["buzzer"].tone(2000, 100)
                            time.sleep(0.1)
                            self.actuators["buzzer"].tone(2000, 100)
                        except: pass
            else:
                self.btn_press_started_at = None

            # Use new edge-detection fell() method
            if self.button.fell():
                log("Button pressed!")
                
                # Prepare event payload
                event_data = {
                    "event_type": "button_press",
                    "payload": {
                        "pin": PIN_BUTTON,
                        "ts": time.time()
                    }
                }
                
                # Post to Django
                if self.api:
                    # Request returns (success, status, info)
                    _, _, _ = self.api.post_event(event_data)
                
                # Beep if buzzer available
                if "buzzer" in self.actuators:
                    try:
                        self.actuators["buzzer"].tone(1500, 50)
                    except:
                        pass
        except Exception as e:
            log("Error reading button: {}".format(e))

    def publish_sensors(self):
        """Read sensors and publish to Django"""
        sensor_values = self.read_sensors()
        
        log(f"Sensor values: {sensor_values}")
        
        # Prepare event data matching Django backend expectations
        event_data = {
            "event_type": "sensor",
            "mq9": sensor_values.get("mq9"),
            "light": sensor_values.get("light"),
            "sound": sensor_values.get("sound"),
            "temp": None,  # Not implemented yet
            "hum": None,   # Not implemented yet
            "payload": {
                "pir": sensor_values.get("pir", False),
                "button": sensor_values.get("button", False)
            }
        }
        
        # Check MQ9 threshold - add safety guard
        try:
            # Ensure threshold is valid before comparison
            if self.mq9_threshold is None or not isinstance(self.mq9_threshold, int):
                log(f"WARNING: Invalid threshold detected: {self.mq9_threshold}, resetting to default")
                self.mq9_threshold = MQ9_THRESHOLD
            
            mq9_val = sensor_values.get("mq9")
            if mq9_val and mq9_val > self.mq9_threshold:
                log(f"WARNING: MQ9 threshold exceeded! {mq9_val} > {self.mq9_threshold}")
                
                # Sound alarm if buzzer available
                if "buzzer" in self.actuators and self.alert_enabled:
                    try:
                        buzzer = self.actuators["buzzer"]
                        # Melody: 800, 1000, 800, 1200, 800 Hz @ 200ms
                        melody = [800, 1000, 800, 1200, 800]
                        for freq in melody:
                            buzzer.tone(freq, 200)
                            time.sleep(0.05)
                    except Exception as e:
                        log(f"Buzzer error: {e}")
                
                # Post alarm event
                if self.api:
                    try:
                        alarm_data = {
                            "event_type": "mq9_alarm",
                            "mq9": mq9_val,
                            "payload": {
                                "threshold": self.mq9_threshold,
                                "value": mq9_val
                            }
                        }
                        # Unpack tuple to avoid ValueError: too many values to unpack (expected 3)
                        _, _, _ = self.api.post_event(alarm_data)
                    except Exception as e:
                        log(f"Alarm post error: {e}")
        
        except Exception as e:
            log(f"MQ9 threshold check error: {e}")
        
        # Post sensor data - localize exception
        if self.api:
            try:
                success, status, info = self.api.post_event(event_data)
                if success:
                    log("  ✓ Sensor data posted")
                else:
                    log(f"  ✗ Sensor data post failed: {status} ({info})")
            except Exception as e:
                log(f"  ✗ Sensor post exception: {e}")
    
    def _periodic_check(self):
        """Periodic health checks"""
        try:
            # Check WiFi connection status
            if self.wifi_manager.is_connected():
                log("WiFi connection healthy")
                
                # Try to fetch updated configuration from Django
                # This would update local cache if server has new settings
                if self.api:
                    try:
                        # Periodic config sync (no save to avoid Errno 30)
                        server_config = self.api.fetch_config(save_to_file=False)
                        if server_config:
                            # Update threshold if provided - use safe parsing
                            raw_threshold = server_config.get("mq9_threshold")
                            new_threshold = safe_parse_threshold(raw_threshold, self.mq9_threshold)
                            if new_threshold != self.mq9_threshold:
                                log(f"Updated MQ9 threshold: {self.mq9_threshold} -> {new_threshold}")
                                self.mq9_threshold = new_threshold
                            
                            # Update alert_enabled
                            new_alert = server_config.get("alert_enabled", True)
                            if new_alert != self.alert_enabled:
                                log(f"Updated alert_enabled: {self.alert_enabled} -> {new_alert}")
                                self.alert_enabled = new_alert

                            # Execute pending IR command from server
                            ir_cmd = server_config.get("ir_command")
                            if ir_cmd and ir_cmd.get("action") == "send_ir":
                                try:
                                    code = int(ir_cmd["code"], 0)
                                    log(f"Executing IR command: code={ir_cmd['code']}")
                                    self.send_ir_test(code)
                                except Exception as ir_e:
                                    log(f"IR command execution error: {ir_e}")
                    except Exception as e:
                        log(f"Config sync error: {e}")
                
            else:
                log("WiFi connection lost - attempting reconnection")
                self._attempt_wifi_connection()
                
        except Exception as e:
            log(f"Periodic check error: {e}")
    
    def loop(self):
        """Main event loop with WiFi hardening"""
        log("Starting main loop...")
        
        # Initial WiFi connection attempt
        self._attempt_wifi_connection()
        
        while self.running:
            try:
                now = time.monotonic()
                
                # Check button state every loop - localize exception
                try:
                    self.check_button()
                except Exception as e:
                    log(f"Button check error: {e}")
                
                # Check IR receiver at higher frequency - localize exception
                if now - self.last_ir_time >= IR_CHECK_INTERVAL:
                    try:
                        self.check_ir_receiver()
                        self.last_ir_time = now
                    except Exception as e:
                        log(f"IR check error: {e}")
                        self.last_ir_time = now  # Update anyway to prevent spam
                
                # Publish sensors at lower frequency - localize exception
                if now - self.last_sensor_time >= SENSOR_INTERVAL:
                    try:
                        self.publish_sensors()
                    except Exception as e:
                        log(f"Sensor publish error: {e}")
                    finally:
                        self.last_sensor_time = now
                        # Periodic garbage collection
                        gc.collect()
                
                # Periodic health checks - localize exception
                if now - self.last_check_time >= SETUP_CHECK_INTERVAL:
                    try:
                        self._periodic_check()
                    except Exception as e:
                        log(f"Periodic check error: {e}")
                    finally:
                        self.last_check_time = now
                
                # Small sleep to prevent CPU spinning
                
                # PIR Edge Detection (False -> True) + 5-second status publish
                if "pir" in self.sensors:
                    try:
                        pir_val = self.sensors["pir"].read()
                        # Edge detection: immediate event on False->True
                        if pir_val and not self.last_pir:
                            log("PIR Motion Detected!")
                            event_data = {
                                "event_type": "pir_motion",
                                "pir": True,
                                "payload": {
                                    "ts": time.time(),
                                    "value": True
                                }
                            }
                            if self.api:
                                try:
                                    self.api.post_event(event_data)
                                except: pass
                        # 5-second PIR status publish (independent interval)
                        if now - self.last_pir_publish_time >= PIR_INTERVAL:
                            pir_status_data = {
                                "event_type": "pir_status",
                                "pir": bool(pir_val),
                                "payload": {
                                    "ts": time.time(),
                                    "value": bool(pir_val)
                                }
                            }
                            if self.api:
                                try:
                                    self.api.post_event(pir_status_data)
                                except: pass
                            self.last_pir_publish_time = now
                        self.last_pir = pir_val
                    except Exception as e:
                        log(f"PIR check error: {e}")

                # Learning Mode LED Blink
                if self.learning_mode and self.led:
                     if now - self.led_last_toggle >= LED_BLINK_INTERVAL:
                        self.led_state = not self.led_state
                        self.led.value = self.led_state
                        self.led_last_toggle = now

                time.sleep(0.05)
            
            except KeyboardInterrupt:
                log("Interrupted by user")
                self.running = False
                break
            
            except Exception as e:
                log(f"Loop error: {e}")
                # Don't crash, just wait and retry
                time.sleep(1)
    
    def cleanup(self):
        """Clean up resources"""
        log("Cleaning up...")
        
        # Deinit sensors
        for sensor in self.sensors.values():
            try:
                sensor.deinit()
            except:
                pass
        
        # Deinit actuators
        for actuator in self.actuators.values():
            try:
                actuator.deinit()
            except:
                pass
        
        # Deinit IR
        if self.ir_rx:
            try:
                self.ir_rx.deinit()
            except:
                pass
        
        if self.ir_tx:
            try:
                self.ir_tx.deinit()
            except:
                pass

# ============================
# Entry Point
# ============================
def main():
    log("=== Pico 2 W IoT Device Starting ===")
    
    # Check for Diagnostic Mode
    if secrets.get("DIAGNOSTIC_MODE"):
        log("=" * 60)
        log("  DIAGNOSTIC MODE ACTIVATED")
        log("=" * 60)
        
        try:
            import diagnostics
            diagnostics.run_full_diagnostics(secrets)
        except Exception as e:
            log(f"Diagnostic mode failed: {e}")
            import traceback
            traceback.print_exception(e)
        
        log("")
        log("Diagnostics complete. Set DIAGNOSTIC_MODE=False to return to normal operation.")
        log("Entering sleep mode. Reset device to continue.")
        
        # Sleep indefinitely - user must reset device
        while True:
            time.sleep(60)
    
    
    log(f"Device ID: {DEVICE_ID}")
    
    device = IoTDevice()
    
    try:
        # Initialize components
        device.init_sensors()
        device.init_actuators()
        device.init_ir()
        
        log("Initialization complete")
        
        # Optional: Send test IR signal at startup (comment out if not needed)
        # device.send_ir_test(0x20DF10EF)
        
        # Run main loop
        device.loop()
    
    except Exception as e:
        log(f"Fatal error: {e}")
        import traceback
        traceback.print_exception(e)
    
    finally:
        device.cleanup()
        log("Device stopped")

if __name__ == "__main__":
    main()