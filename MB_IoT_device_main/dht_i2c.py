# dht_i2c.py
# I2C temperature/humidity sensor (SHT31/DHT20 etc.)
# Uses centralized I2C bus management

import time
import i2c_bus

# Supported sensor addresses
SHT31_ADDR = 0x44
DHT20_ADDR = 0x38

_sensor = None
_sensor_type = None

def init(channel=None):
    """
    Initialize I2C temperature/humidity sensor
    channel: TCA9548A channel (None for direct connection)
    Returns sensor instance or None
    """
    global _sensor, _sensor_type

    # Select mux channel if specified
    if channel is not None:
        if not i2c_bus.select_channel(channel):
            print("DHT: Failed to select mux channel", channel)
            return None

    i2c = i2c_bus.get_i2c()
    if i2c is None:
        print("DHT: I2C bus not available")
        return None

    # Try SHT31 first
    try:
        # Check if SHT31 is present
        i2c.writeto(SHT31_ADDR, bytes([0xF3, 0x2D]))  # Soft reset
        time.sleep(0.01)
        _sensor = SHT31_ADDR
        _sensor_type = "SHT31"
        print("DHT: SHT31 sensor initialized")
        return _sensor
    except Exception:
        pass

    # Try DHT20
    try:
        # Check if DHT20 is present
        i2c.writeto(DHT20_ADDR, bytes([0x71]))  # Status register
        time.sleep(0.01)
        _sensor = DHT20_ADDR
        _sensor_type = "DHT20"
        print("DHT: DHT20 sensor initialized")
        return _sensor
    except Exception:
        pass

    print("DHT: No supported sensor found")
    return None

def read(sensor=None):
    """
    Read temperature and humidity
    Returns (temperature, humidity) or (None, None)
    """
    if _sensor is None:
        return None, None

    i2c = i2c_bus.get_i2c()
    if i2c is None:
        return None, None

    try:
        if _sensor_type == "SHT31":
            # SHT31 measurement command
            i2c.writeto(_sensor, bytes([0x24, 0x00]))  # High repeatability
            time.sleep(0.5)  # Wait for measurement

            # Read 6 bytes
            result = bytearray(6)
            i2c.readfrom_into(_sensor, result)

            # Convert to temperature and humidity
            temp_raw = (result[0] << 8) | result[1]
            hum_raw = (result[3] << 8) | result[4]

            temperature = -45 + (175 * temp_raw / 65535.0)
            humidity = 100 * hum_raw / 65535.0

            return round(temperature, 1), round(humidity, 1)

        elif _sensor_type == "DHT20":
            # DHT20 measurement
            i2c.writeto(_sensor, bytes([0xAC, 0x33, 0x00]))  # Trigger measurement
            time.sleep(0.08)  # Wait for measurement

            # Read 7 bytes
            result = bytearray(7)
            i2c.readfrom_into(_sensor, result)

            # Convert (simplified, actual conversion is more complex)
            hum_raw = (result[1] << 12) | (result[2] << 4) | (result[3] >> 4)
            temp_raw = ((result[3] & 0x0F) << 16) | (result[4] << 8) | result[5]

            humidity = hum_raw * 100 / 1048576.0
            temperature = temp_raw * 200 / 1048576.0 - 50

            return round(temperature, 1), round(humidity, 1)

    except Exception as e:
        print("DHT read error:", e)
        return None, None

    return None, None
