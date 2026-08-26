"""Automotive example: OBD-II via CAN bus.

Hardware setup:
- OBD-II to CAN adapter (e.g., ELM327, CANable)
- Connect to vehicle's OBD-II port
- Linux SocketCAN setup:
  sudo modprobe can
  sudo ip link set can0 type can bitrate 500000
  sudo ip link set can0 up
"""

from glinx import Glinx

app = Glinx()

@app.sensor(
    "vehicle_obd2",
    protocol="can",
    interface="can0",
    bitrate=500000,  # 500 kbps (OBD-II standard)
    protocol="obd2",
    filter_ids=[0x7E8, 0x7E9],  # OBD-II response IDs
    sensor_type="automotive",
    location="vehicle.diagnostics",
)
def vehicle_obd2(raw):
    """C++ driver handles CAN bus at automotive speeds."""
    return raw


@app.rule("vehicle_obd2", when="engine_rpm > 6000", priority="MEDIUM")
def high_rpm_warning(event):
    return "Engine RPM exceeds 6000"


@app.rule("vehicle_obd2", when="coolant_temperature_c > 100", priority="HIGH")
def overheating_warning(event):
    return "Engine coolant temperature critically high"


@app.rule("vehicle_obd2", when="vehicle_speed_kph > 120", priority="MEDIUM")
def speeding_warning(event):
    return "Vehicle speed exceeds 120 km/h"


@app.summary(["vehicle_obd2"], interval_seconds=5, label="vehicle_status")
def vehicle_summary(event):
    return "5-second vehicle diagnostics summary"


if __name__ == "__main__":
    print("Starting OBD-II monitoring via CAN bus...")
    print("Using C++ SocketCAN driver for real-time automotive data")
    print()
    
    # Expose to AI agents
    app.serve()
    
    # Agent can now query:
    # - get_vehicle_obd2_status() → latest RPM, speed, temp, etc.
    # - drain_glinx_events() → warnings and anomalies
