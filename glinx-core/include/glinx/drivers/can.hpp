#pragma once

#include "../driver.hpp"
#include <cstdint>
#include <vector>

namespace glinx {

/**
 * CAN bus driver for automotive and industrial applications.
 * Uses SocketCAN on Linux.
 */
class CANDriver : public Driver {
public:
    explicit CANDriver(const DriverConfig& config, SensorBuffer* buffer);
    ~CANDriver() override;

    json get_stats() const override;

protected:
    void poll_loop() override;

private:
    bool open_can();
    void close_can();
    bool set_filters();
    json parse_can_frame(uint32_t can_id, const uint8_t* data, size_t len);
    
    // OBD-II specific
    json parse_obd2(uint8_t mode, uint8_t pid, const uint8_t* data, size_t len);

    std::string interface_;  // "can0", "can1", etc.
    uint32_t bitrate_;
    std::vector<uint32_t> filter_ids_;  // CAN IDs to accept
    std::string protocol_;  // "raw", "obd2", "j1939"
    
    int socket_fd_{-1};
    std::atomic<uint64_t> frames_received_{0};
    std::atomic<uint64_t> can_errors_{0};
};

/**
 * OBD-II PID definitions for automotive diagnostics.
 */
namespace OBD2 {
    constexpr uint8_t MODE_CURRENT_DATA = 0x01;
    constexpr uint8_t MODE_FREEZE_FRAME = 0x02;
    constexpr uint8_t MODE_STORED_DTCS = 0x03;
    
    constexpr uint8_t PID_ENGINE_RPM = 0x0C;
    constexpr uint8_t PID_VEHICLE_SPEED = 0x0D;
    constexpr uint8_t PID_THROTTLE_POS = 0x11;
    constexpr uint8_t PID_ENGINE_COOLANT_TEMP = 0x05;
    constexpr uint8_t PID_FUEL_PRESSURE = 0x0A;
    constexpr uint8_t PID_INTAKE_MANIFOLD_PRESSURE = 0x0B;
}

} // namespace glinx
