# Dependencies for Pico 2 W IoT Device

This document lists all dependencies required for the Pico 2 W IoT device to function properly.

## CircuitPython Libraries (Required)

These libraries must be present in the `lib/` directory on the CIRCUITPY drive:

### Core Libraries
- `adafruit_requests.mpy` - HTTP requests for API communication
- `adafruit_connection_manager.mpy` - Connection management for requests
- `adafruit_ticks.py` - Time utilities

### Display Libraries (if using LCD)
- `adafruit_character_lcd/` - Character LCD display support
- `adafruit_mcp230xx/` - MCP23008/MCP23017 I/O expander support

### MQTT Libraries (if using MQTT)
- `adafruit_minimqtt/` - MQTT client for IoT communication

## Built-in CircuitPython Modules

These are included with CircuitPython and don't need to be installed:

### Core Modules
- `wifi` - WiFi radio control
- `socketpool` - Socket management
- `ssl` - SSL/TLS support
- `ipaddress` - IP address utilities
- `microcontroller` - Hardware control and reset
- `board` - Pin definitions
- `digitalio` - Digital I/O control
- `analogio` - Analog I/O control
- `time` - Time functions
- `json` - JSON parsing
- `os` - Operating system interface

### Standard Python Modules
- `gc` - Garbage collection
- `re` - Regular expressions
- `enum` - Enumeration support
- `dataclasses` - Data class support
- `typing` - Type hints
- `abc` - Abstract base classes

## Hardware Dependencies

### Required Hardware
- **Raspberry Pi Pico 2 W** - Main microcontroller with WiFi
- **USB Cable** - For programming and power
- **WiFi Network** - 2.4GHz network for connectivity

### Optional Hardware
- **MQ9 Gas Sensor** - Air quality monitoring (Pin 26)
- **Light Sensor** - Ambient light detection (Pin 27)
- **Sound Sensor** - Audio level monitoring (Pin 28)
- **PIR Motion Sensor** - Motion detection (Pin 22)
- **Push Button** - Manual input (Pin 5)
- **Buzzer** - Audio alerts (Pin 20)
- **IR Receiver** - Infrared signal reception (Pin 15)
- **IR Transmitter** - Infrared signal transmission (Pin 14)
- **LCD Display** - Status display (I2C)

## Software Dependencies

### Development Environment
- **CircuitPython 8.0+** - Firmware for Pico 2 W
- **Python 3.8+** - For development tools
- **rsync** - For deployment synchronization

### Server Dependencies (Optional)
- **Django Server** - Backend API for device management
- **HTTPS Support** - Secure communication
- **API Authentication** - Token-based auth system

## Library Installation

### Method 1: CircuitPython Bundle
1. Download the CircuitPython Bundle from [circuitpython.org](https://circuitpython.org/libraries)
2. Extract the bundle
3. Copy required `.mpy` files to `CIRCUITPY/lib/`

### Method 2: Individual Downloads
Download individual libraries from the Adafruit CircuitPython Library Bundle:
- [adafruit_requests](https://github.com/adafruit/Adafruit_CircuitPython_Requests)
- [adafruit_connection_manager](https://github.com/adafruit/Adafruit_CircuitPython_ConnectionManager)

### Method 3: Automated Installation
Use the CircuitPython library manager (if available):
```bash
circup install adafruit_requests adafruit_connection_manager
```

## Version Compatibility

### CircuitPython Version
- **Minimum**: CircuitPython 8.0.0
- **Recommended**: CircuitPython 8.2.0 or later
- **Tested**: CircuitPython 8.2.6

### Library Versions
- `adafruit_requests`: 1.12.0+
- `adafruit_connection_manager`: 1.0.0+
- `adafruit_minimqtt`: 7.0.0+ (if using MQTT)

## Memory Requirements

### Flash Memory
- **CircuitPython Firmware**: ~1.5MB
- **Application Code**: ~200KB
- **Libraries**: ~500KB
- **Free Space Required**: ~500KB (for logs, configs, etc.)

### RAM Usage
- **Base System**: ~100KB
- **WiFi Stack**: ~50KB
- **Application**: ~30KB
- **Buffers**: ~20KB
- **Available**: ~100KB (on Pico 2 W with 264KB total)

## Network Requirements

### WiFi Network
- **Frequency**: 2.4GHz (5GHz not supported)
- **Security**: WPA2/WPA3 Personal
- **DHCP**: Required for automatic IP assignment
- **Internet Access**: Required for server communication

### Firewall/Router Configuration
- **Outbound HTTPS (443)**: Required for server API calls
- **Outbound HTTP (80)**: Optional for non-secure communication
- **DNS Resolution**: Required for domain name resolution

## Optional Dependencies

### Development Tools
- **Serial Monitor**: For debugging (screen, minicom, etc.)
- **Text Editor**: For configuration editing
- **Git**: For version control
- **Python IDE**: For development (VS Code, PyCharm, etc.)

### Testing Tools
- **WiFi Analyzer**: For network troubleshooting
- **HTTP Client**: For API testing (curl, Postman, etc.)
- **Multimeter**: For hardware debugging

## Troubleshooting Dependencies

### Missing Libraries
```python
# Error: ImportError: No module named 'adafruit_requests'
# Solution: Copy adafruit_requests.mpy to CIRCUITPY/lib/
```

### Memory Issues
```python
# Error: MemoryError
# Solutions:
# 1. Remove unused libraries from lib/
# 2. Use .mpy files instead of .py files
# 3. Reduce buffer sizes in code
```

### WiFi Issues
```python
# Error: WiFi connection failed
# Check:
# 1. Network is 2.4GHz
# 2. Credentials are correct
# 3. Network is in range
# 4. Router supports WPA2/WPA3
```

## Dependency Updates

### Regular Updates
- Check for CircuitPython firmware updates monthly
- Update libraries quarterly or when issues arise
- Monitor Adafruit GitHub repositories for security updates

### Update Process
1. Backup current configuration
2. Download new firmware/libraries
3. Test in development environment
4. Deploy to production devices
5. Verify functionality

## Security Considerations

### Library Sources
- Only use official Adafruit libraries
- Verify checksums when possible
- Avoid third-party modifications

### Network Security
- Use WPA3 when available
- Regularly rotate WiFi passwords
- Monitor network traffic for anomalies
- Use HTTPS for all server communication

## Support Resources

### Official Documentation
- [CircuitPython Documentation](https://docs.circuitpython.org/)
- [Adafruit Learning System](https://learn.adafruit.com/)
- [Raspberry Pi Pico Documentation](https://www.raspberrypi.org/documentation/microcontrollers/)

### Community Support
- [CircuitPython Discord](https://discord.gg/circuitpython)
- [Adafruit Forums](https://forums.adafruit.com/)
- [Reddit r/CircuitPython](https://reddit.com/r/circuitpython)

### Issue Reporting
- [CircuitPython Issues](https://github.com/adafruit/circuitpython/issues)
- [Library Issues](https://github.com/adafruit/Adafruit_CircuitPython_Bundle/issues)
- Project-specific issues: Use project repository