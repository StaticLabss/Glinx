#include "glinx/drivers/i2c.hpp"
#include <spdlog/spdlog.h>
#include <thread>
#include <chrono>

#ifdef __linux__
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/i2c-dev.h>
#endif

namespace glinx {

I2CDriver::I2CDriver(const DriverConfig& config, SensorBuffer* buffer)
    : Driver(config, buffer) {
    
    bus_ = config_.options.value("bus", "/dev/i2c-1");
    device_address_ = config_.options.value("device_address", 0x68);
    register_address_ = config_.options.value("register_address", 0x00);
    read_length_ = config_.options.value("read_length", 6);
    poll_interval_us_ = config_.options.value("poll_interval_us", 10000); // 10ms default = 100Hz
    sensor_type_ = config_.options.value("sensor_type", "generic");
}

I2CDriver::~I2CDriver() {
    close_bus();
}

bool I2CDriver::open_bus() {
#ifdef __linux__
    fd_ = ::open(bus_.c_str(), O_RDWR);
    
    if (fd_ < 0) {
        spdlog::error("Failed to open I2C bus {}", bus_);
        return false;
    }
    
    if (ioctl(fd_, I2C_SLAVE, device_address_) < 0) {
        spdlog::error("Failed to set I2C slave address 0x{:02X}", device_address_);
        ::close(fd_);
        fd_ = -1;
        return false;
    }
    
    spdlog::info("Opened I2C bus {} with device 0x{:02X}", bus_, device_address_);
    return true;
#else
    spdlog::error("I2C driver is only supported on Linux");
    return false;
#endif
}

void I2CDriver::close_bus() {
#ifdef __linux__
    if (fd_ >= 0) {
        ::close(fd_);
        fd_ = -1;
    }
#endif
}

bool I2CDriver::read_register(uint8_t reg, uint8_t* data, size_t len) {
#ifdef __linux__
    if (::write(fd_, &reg, 1) != 1) {
        i2c_errors_.fetch_add(1);
        return false;
    }
    
    if (::read(fd_, data, len) != static_cast<ssize_t>(len)) {
        i2c_errors_.fetch_add(1);
        return false;
    }
    
    reads_.fetch_add(1);
    return true;
#else
    (void)reg;
    (void)data;
    (void)len;
    return false;
#endif
}

json I2CDriver::parse_sensor_data(const uint8_t* data, size_t len) {
    json result;
    
    // MPU6050/MPU9250 (6-axis IMU)
    if (sensor_type_ == "mpu6050" || sensor_type_ == "mpu9250") {
        if (len >= 6) {
            int16_t ax = (data[0] << 8) | data[1];
            int16_t ay = (data[2] << 8) | data[3];
            int16_t az = (data[4] << 8) | data[5];
            
            result["accel_x"] = ax / 16384.0; // ±2g range
            result["accel_y"] = ay / 16384.0;
            result["accel_z"] = az / 16384.0;
        }
        if (len >= 12) {
            int16_t gx = (data[6] << 8) | data[7];
            int16_t gy = (data[8] << 8) | data[9];
            int16_t gz = (data[10] << 8) | data[11];
            
            result["gyro_x"] = gx / 131.0; // ±250°/s range
            result["gyro_y"] = gy / 131.0;
            result["gyro_z"] = gz / 131.0;
        }
    }
    // BMP280 (pressure/temperature)
    else if (sensor_type_ == "bmp280") {
        if (len >= 3) {
            int32_t adc_p = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4);
            result["pressure_raw"] = adc_p;
        }
        if (len >= 6) {
            int32_t adc_t = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4);
            result["temperature_raw"] = adc_t;
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

void I2CDriver::poll_loop() {
    if (!open_bus()) {
        return;
    }
    
    std::vector<uint8_t> buffer(read_length_);
    
    while (!stop_requested()) {
        if (read_register(register_address_, buffer.data(), read_length_)) {
            json parsed = parse_sensor_data(buffer.data(), read_length_);
            
            SensorMessage msg;
            std::strncpy(msg.source_id, config_.source_id.c_str(), sizeof(msg.source_id) - 1);
            std::strncpy(msg.protocol, "i2c", sizeof(msg.protocol) - 1);
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

json I2CDriver::get_stats() const {
    auto stats = Driver::get_stats();
    stats["bus"] = bus_;
    stats["device_address"] = device_address_;
    stats["reads"] = reads_.load();
    stats["i2c_errors"] = i2c_errors_.load();
    return stats;
}

} // namespace glinx
