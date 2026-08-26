#pragma once

#include "../driver.hpp"
#include <cstdint>

namespace glinx {

/**
 * SPI driver for high-speed sensor communication.
 * Uses /dev/spidev* devices on Linux.
 */
class SPIDriver : public Driver {
public:
    explicit SPIDriver(const DriverConfig& config, SensorBuffer* buffer);
    ~SPIDriver() override;

    json get_stats() const override;

protected:
    void poll_loop() override;

private:
    bool open_bus();
    void close_bus();
    bool transfer(const uint8_t* tx_data, uint8_t* rx_data, size_t len);
    json parse_sensor_data(const uint8_t* data, size_t len);

    std::string bus_;
    uint8_t mode_;
    uint32_t speed_hz_;
    uint8_t bits_per_word_;
    int poll_interval_us_;
    std::string sensor_type_;

    int fd_{-1};
    std::atomic<uint64_t> transfers_{0};
    std::atomic<uint64_t> spi_errors_{0};
};

} // namespace glinx
