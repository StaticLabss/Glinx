"""ESP32 MPU6050 via MQTT (WiFi).

Hardware setup:
1. Upload examples/esp32_sketches/esp32_mpu6050_wifi.ino to ESP32
2. Update WiFi credentials and MQTT broker IP in the sketch
3. Install MQTT broker (mosquitto): sudo apt install mosquitto mosquitto-clients
4. Run this script

This demonstrates wireless IoT data collection.
"""

from glinx import Glinx

app = Glinx()

@app.sensor(
    "esp32_imu",
    protocol="mqtt",
    broker="192.168.1.100",  # Your MQTT broker
    topics=["sensor/imu"],
    fields={
        "accel_x": "acceleration_x_ms2",
        "accel_y": "acceleration_y_ms2",
        "accel_z": "acceleration_z_ms2",
        "gyro_x": "angular_velocity_x_rads",
        "gyro_y": "angular_velocity_y_rads",
        "gyro_z": "angular_velocity_z_rads",
        "temp_c": "temperature_celsius",
    },
    sensor_type="imu",
    location="device.imu",
    unit="m/s^2, rad/s, C",
)
def esp32_imu(raw):
    """Python MQTT driver handles network I/O."""
    return raw


@app.rule("esp32_imu", when="abs(acceleration_z_ms2) > 15", priority="HIGH")
def fall_detected(event):
    return "Fall or impact detected"


@app.rule("esp32_imu", when="abs(angular_velocity_x_rads) > 3.5", priority="MEDIUM")
def rapid_rotation(event):
    return "Rapid rotation detected"


@app.summary(["esp32_imu"], interval_seconds=10, label="imu_summary")
def imu_status(event):
    return "10-second IMU summary"


if __name__ == "__main__":
    print("Starting ESP32 IMU monitoring via MQTT...")
    print("Wireless data collection at 20 Hz")
    print()
    
    # Start MCP server
    app.serve()
