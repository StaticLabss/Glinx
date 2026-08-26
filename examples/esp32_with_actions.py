"""ESP32 with bidirectional control - agent can read sensors AND control actuators.

Hardware setup:
- ESP32 with DHT22 sensor
- LED on GPIO 2 (built-in on most ESP32 boards)
- Upload sketch that listens on Serial for commands

This demonstrates the full loop: sensor -> agent -> action -> hardware
"""

from glinx import Glinx
import serial
import json

app = Glinx()

# Global serial connection for actions
esp32_serial = None

def init_serial():
    """Initialize serial connection."""
    global esp32_serial
    if esp32_serial is None:
        esp32_serial = serial.Serial("COM3", 115200, timeout=1)
    return esp32_serial


@app.sensor(
    "esp32_env",
    protocol="serial",
    port="COM3",
    baudrate=115200,
    parser="json",
    fields={
        "temperature_c": "temperature",
        "humidity_pct": "humidity",
    },
    sensor_type="environmental",
    location="room",
)
def esp32_env(raw):
    return raw


# Define actions the agent can call
@app.action("led_on")
def led_on():
    """Turn on ESP32 built-in LED."""
    ser = init_serial()
    command = {"action": "led", "state": "on"}
    ser.write((json.dumps(command) + "\n").encode())
    return {"status": "LED turned on"}


@app.action("led_off")
def led_off():
    """Turn off ESP32 built-in LED."""
    ser = init_serial()
    command = {"action": "led", "state": "off"}
    ser.write((json.dumps(command) + "\n").encode())
    return {"status": "LED turned off"}


@app.action("set_led_brightness")
def set_led_brightness(brightness: int):
    """Set LED brightness (0-255).
    
    Args:
        brightness: PWM value 0-255
    """
    if not 0 <= brightness <= 255:
        return {"status": "error", "error": "Brightness must be 0-255"}
    
    ser = init_serial()
    command = {"action": "led_pwm", "value": brightness}
    ser.write((json.dumps(command) + "\n").encode())
    return {"status": f"LED brightness set to {brightness}"}


# Automatic action based on sensor reading
@app.rule("esp32_env", when="temperature > 28", priority="MEDIUM")
def high_temp_alert(event):
    """Trigger LED when temperature is high."""
    led_on()  # Automatically turn on LED
    return "Temperature high - LED activated"


@app.on_event("high_temp_alert")
def handle_high_temp(event):
    print(f"Alert: {event.description}")
    print("LED turned on as visual indicator")


if __name__ == "__main__":
    print("Starting ESP32 with bidirectional control...")
    print("Agent can:")
    print("  - Read: get_esp32_env_status()")
    print("  - Control: led_on(), led_off(), set_led_brightness()")
    print()
    
    app.serve()
