#pragma once

#include "../driver.hpp"
#include <cstdint>

namespace glinx {

/**
 * I2C driver for direct hardware access on Linux (Raspberry Pi, etc.).
 * Uses /dev/i2c-* devices.
 */
class I2CDriver : public Driver {
public:
    explicit I2CDriver(const DriverConfig& config, SensorBuffer* buffer);
    ~I2CDriver() override;

    json get_stats() const override;

protected:
    void poll_loop() override;

private:
    bool open_bus();
    void close_bus();
    bool read_register(uint8_t reg, uint8_t* data, size_t len);
    json parse_sensor_data(const uint8_t* data, size_t len);

    std::string bus_;
    uint8_t device_address_;
    uint8_t register_address_;
    size_t read_length_;
    int poll_interval_us_;
    std::string sensor_type_; // "mpu6050", "bmp280", etc.

    int fd_{-1};
    std::atomic<uint64_t> reads_{0};
    std::atomic<uint64_t> i2c_errors_{0};
};

} // namespace glinx
