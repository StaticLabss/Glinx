#include "glinx/drivers/spi.hpp"
#include <spdlog/spdlog.h>
#include <thread>
#include <chrono>

#ifdef __linux__
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/spi/spidev.h>
#endif

namespace glinx {

SPIDriver::SPIDriver(const DriverConfig& config, SensorBuffer* buffer)
    : Driver(config, buffer) {
    
    bus_ = config_.options.value("bus", "/dev/spidev0.0");
    mode_ = config_.options.value("mode", 0);
    speed_hz_ = config_.options.value("speed_hz", 1000000); // 1MHz default
    bits_per_word_ = config_.options.value("bits_per_word", 8);
    poll_interval_us_ = config_.options.value("poll_interval_us", 1000); // 1ms = 1kHz
    sensor_type_ = config_.options.value("sensor_type", "generic");
}

SPIDriver::~SPIDriver() {
    close_bus();
}

bool SPIDriver::open_bus() {
#ifdef __linux__
    fd_ = ::open(bus_.c_str(), O_RDWR);
    
    if (fd_ < 0) {
        spdlog::error("Failed to open SPI bus {}", bus_);
        return false;
    }
    
    // Set SPI mode
    if (ioctl(fd_, SPI_IOC_WR_MODE, &mode_) < 0) {
        spdlog::error("Failed to set SPI mode");
        close_bus();
        return false;
    }
    
    // Set bits per word
    if (ioctl(fd_, SPI_IOC_WR_BITS_PER_WORD, &bits_per_word_) < 0) {
        spdlog::error("Failed to set SPI bits per word");
        close_bus();
        return false;
    }
    
    // Set max speed
    if (ioctl(fd_, SPI_IOC_WR_MAX_SPEED_HZ, &speed_hz_) < 0) {
        spdlog::error("Failed to set SPI speed");
        close_bus();
        return false;
    }
    
    spdlog::info("Opened SPI bus {} @ {} Hz", bus_, speed_hz_);
    return true;
#else
    spdlog::error("SPI driver is only supported on Linux");
    return false;
#endif
}

void SPIDriver::close_bus() {
#ifdef __linux__
    if (fd_ >= 0) {
        ::close(fd_);
        fd_ = -1;
    }
#endif
}

bool SPIDriver::transfer(const uint8_t* tx_data, uint8_t* rx_data, size_t len) {
#ifdef __linux__
    struct spi_ioc_transfer tr = {};
    tr.tx_buf = reinterpret_cast<unsigned long>(tx_data);
    tr.rx_buf = reinterpret_cast<unsigned long>(rx_data);
    tr.len = len;
    tr.speed_hz = speed_hz_;
    tr.bits_per_word = bits_per_word_;
    
    if (ioctl(fd_, SPI_IOC_MESSAGE(1), &tr) < 0) {
        spi_errors_.fetch_add(1);
        return false;
    }
    
    transfers_.fetch_add(1);
    return true;
#else
    (void)tx_data;
    (void)rx_data;
    (void)len;
    return false;
#endif
}

json SPIDriver::parse_sensor_data(const uint8_t* data, size_t len) {
    json result;
    
    // MAX31855 (thermocouple)
    if (sensor_type_ == "max31855" && len >= 4) {
        int32_t raw = (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3];
        
        if (raw & 0x80000000) {
            result["fault"] = true;
        } else {
            int16_t temp = (raw >> 18) & 0x3FFF;
            if (temp & 0x2000) temp |= 0xC000; // Sign extend
            result["temperature_c"] = temp * 0.25;
            
            int16_t internal = (raw >> 4) & 0xFFF;
            if (internal & 0x800) internal |= 0xF000;
            result["internal_temp_c"] = internal * 0.0625;
        }
    }
    // Generic: raw bytes
    else {
        for (size_t i = 0; i < len; ++i) {
            result["byte_" + std::to_string(i)] = data[i];
        }
    }
    
    return result;
}

void SPIDriver::poll_loop() {
    if (!open_bus()) {
        return;
    }
    
    std::vector<uint8_t> tx_buffer(32, 0);
    std::vector<uint8_t> rx_buffer(32, 0);
    
    while (!stop_requested()) {
        if (transfer(tx_buffer.data(), rx_buffer.data(), tx_buffer.size())) {
            json parsed = parse_sensor_data(rx_buffer.data(), rx_buffer.size());
            
            SensorMessage msg;
            std::strncpy(msg.source_id, config_.source_id.c_str(), sizeof(msg.source_id) - 1);
            std::strncpy(msg.protocol, "spi", sizeof(msg.protocol) - 1);
            msg.timestamp = get_timestamp();
            
            std::string payload_str = parsed.dump();
            msg.payload_size = std::min(payload_str.size(), sizeof(msg.payload));
            std::memcpy(msg.payload, payload_str.data(), msg.payload_size);
            
            push_message(msg);
        }
        
        std::this_thread::sleep_for(std::chrono::microseconds(poll_interval_us_));
    }
    
    close_bus();
}

json SPIDriver::get_stats() const {
    auto stats = Driver::get_stats();
    stats["bus"] = bus_;
    stats["speed_hz"] = speed_hz_;
    stats["transfers"] = transfers_.load();
    stats["spi_errors"] = spi_errors_.load();
    return stats;
}

} // namespace glinx
