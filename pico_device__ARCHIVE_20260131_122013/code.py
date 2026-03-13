# Main CircuitPython application for Pico 2 W WiFi Hardening
# Ensures reliable Setup AP fallback and Django integration

import time
import board
import digitalio
import microcontroller
from pico_device.config_manager import ConfigurationManager, DjangoConfigSource, LocalFileConfigSource, SecretsConfigSource
from pico_device.wifi_manager import WiFiManager
from pico_device.setup_ap import SetupAPHandler

# Device configuration
DEVICE_ID = "PICO001"  # Should be unique per device
WIFI_FAILURE_THRESHOLD = 3
SETUP_CHECK_INTERVAL = 30  # seconds

class PicoWiFiHardening:
    """Main application class for Pico 2 W WiFi hardening"""
    
    def __init__(self):
        self.device_id = DEVICE_ID
        self.config_manager = None
        self.wifi_manager = None
        self.setup_handler = None
        self.led = None
        self.button = None
        self.last_check_time = 0
        
        # Initialize hardware
        self._init_hardware()
        
        # Initialize managers
        self._init_managers()
        
        print(f"[MAIN] Pico WiFi Hardening initialized - Device ID: {self.device_id}")
    
    def _init_hardware(self):
        """Initialize hardware components"""
        try:
            # Initialize LED for status indication
            self.led = digitalio.DigitalInOut(board.LED)
            self.led.direction = digitalio.Direction.OUTPUT
            self.led.value = False
            
            # Initialize button for manual setup trigger (if available)
            # Note: Adjust pin based on your hardware setup
            # self.button = digitalio.DigitalInOut(board.GP15)
            # self.button.direction = digitalio.Direction.INPUT
            # self.button.pull = digitalio.Pull.UP
            
            print("[MAIN] Hardware initialized")
        except Exception as e:
            print(f"[MAIN] Hardware init error: {e}")
    
    def _init_managers(self):
        """Initialize configuration and WiFi managers"""
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
            
            print("[MAIN] Managers initialized")
        except Exception as e:
            print(f"[MAIN] Manager init error: {e}")
            # Force setup mode if initialization fails
            self._enter_setup_mode("INIT_ERROR")
    
    def run(self):
        """Main application loop"""
        print("[MAIN] Starting main application loop")
        
        # Initial WiFi connection attempt
        self._attempt_wifi_connection()
        
        while True:
            try:
                current_time = time.monotonic()
                
                # Periodic checks
                if current_time - self.last_check_time >= SETUP_CHECK_INTERVAL:
                    self._periodic_check()
                    self.last_check_time = current_time
                
                # Check for user-triggered setup
                if self._check_user_setup_trigger():
                    self._enter_setup_mode("USER_TRIGGERED")
                
                # Update LED status
                self._update_led_status()
                
                # Small delay to prevent busy loop
                time.sleep(1)
                
            except KeyboardInterrupt:
                print("[MAIN] Application interrupted")
                break
            except Exception as e:
                print(f"[MAIN] Main loop error: {e}")
                time.sleep(5)  # Wait before retrying
    
    def _attempt_wifi_connection(self):
        """Attempt WiFi connection with Setup AP fallback"""
        print("[MAIN] Attempting WiFi connection...")
        
        try:
            # Check if we should enter setup mode immediately
            if self.wifi_manager.should_enter_setup_mode():
                reason = self.wifi_manager.setup_reason or "UNKNOWN"
                self._enter_setup_mode(reason)
                return
            
            # Attempt WiFi connection
            success = self.wifi_manager.connect_wifi()
            
            if success:
                print(f"[MAIN] WiFi connected successfully to {self.wifi_manager.get_current_ssid()}")
                self._on_wifi_connected()
            else:
                print("[MAIN] WiFi connection failed")
                
                # Check if we should enter setup mode after failure
                if self.wifi_manager.should_enter_setup_mode():
                    reason = self.wifi_manager.setup_reason or "CONNECTION_FAILED"
                    self._enter_setup_mode(reason)
                
        except Exception as e:
            print(f"[MAIN] WiFi connection error: {e}")
            self._enter_setup_mode("WIFI_ERROR")
    
    def _enter_setup_mode(self, reason: str):
        """Enter Setup AP mode - CRITICAL: Must be reliable"""
        print(f"[MAIN] *** ENTERING SETUP MODE *** Reason: {reason}")
        
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
            print(f"[MAIN] CRITICAL: Setup mode error: {e}")
            # Last resort - restart device
            print("[MAIN] Restarting device...")
            microcontroller.reset()
    
    def _setup_mode_loop(self):
        """Loop while in setup mode"""
        print("[MAIN] Setup mode active - waiting for configuration...")
        
        while True:
            try:
                # Blink LED to indicate setup mode
                self.led.value = not self.led.value
                time.sleep(0.5)
                
                # Check for configuration updates
                # In real implementation, this would check for web form submissions
                # and call self.setup_handler.handle_config_update()
                
                # For now, just maintain setup mode
                # TODO: Implement web server request handling
                
            except KeyboardInterrupt:
                print("[MAIN] Setup mode interrupted")
                break
            except Exception as e:
                print(f"[MAIN] Setup mode loop error: {e}")
                time.sleep(1)
    
    def _periodic_check(self):
        """Periodic health checks"""
        try:
            # Check WiFi connection status
            if self.wifi_manager.is_connected():
                print("[MAIN] WiFi connection healthy")
                
                # Try to fetch updated configuration from Django
                # This would update local cache if server has new settings
                # TODO: Implement Django config sync
                
            else:
                print("[MAIN] WiFi connection lost - attempting reconnection")
                self._attempt_wifi_connection()
                
        except Exception as e:
            print(f"[MAIN] Periodic check error: {e}")
    
    def _check_user_setup_trigger(self) -> bool:
        """Check if user has triggered setup mode manually"""
        try:
            # Check button press (if button is available)
            if self.button and not self.button.value:
                # Button pressed (assuming active low)
                print("[MAIN] Setup button pressed")
                return True
            
            # Check for setup trigger file
            try:
                with open("force_setup.txt", "r") as f:
                    content = f.read().strip()
                    if content == "FORCE_SETUP":
                        print("[MAIN] Setup trigger file found")
                        # Remove trigger file
                        import os
                        os.remove("force_setup.txt")
                        return True
            except OSError:
                pass  # File doesn't exist
            
            return False
            
        except Exception as e:
            print(f"[MAIN] User trigger check error: {e}")
            return False
    
    def _update_led_status(self):
        """Update LED to indicate current status"""
        try:
            if self.wifi_manager.is_connected():
                # Solid on when connected
                self.led.value = True
            elif self.wifi_manager.connection_state.value == "setup_mode":
                # Already blinking in setup mode loop
                pass
            else:
                # Slow blink when disconnected
                self.led.value = not self.led.value
                
        except Exception as e:
            print(f"[MAIN] LED update error: {e}")
    
    def _on_wifi_connected(self):
        """Called when WiFi connection is established"""
        try:
            print("[MAIN] WiFi connected - performing post-connection setup")
            
            # Reset failure count
            self.wifi_manager.reset_failure_count()
            
            # TODO: Sync with Django server
            # TODO: Update local configuration cache
            # TODO: Start any background tasks
            
        except Exception as e:
            print(f"[MAIN] Post-connection setup error: {e}")

def main():
    """Main entry point"""
    print("=" * 50)
    print("Pico 2 W WiFi Hardening System")
    print("Ensuring reliable Setup AP fallback")
    print("=" * 50)
    
    try:
        app = PicoWiFiHardening()
        app.run()
    except Exception as e:
        print(f"[MAIN] FATAL ERROR: {e}")
        print("[MAIN] Restarting in 5 seconds...")
        time.sleep(5)
        microcontroller.reset()

# Auto-run when imported as main module
if __name__ == "__main__":
    main()