#pragma once

#include "../driver.hpp"
#include <string>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#else
#include <termios.h>
#endif

namespace glinx {

/**
 * High-performance serial/UART driver.
 * Supports JSON and CSV parsing in C++ for minimal latency.
 */
class SerialDriver : public Driver {
public:
    explicit SerialDriver(const DriverConfig& config, SensorBuffer* buffer);
    ~SerialDriver() override;

    json get_stats() const override;

protected:
    void poll_loop() override;

private:
    bool open_port();
    void close_port();
    bool read_line(std::string& line);
    json parse_line(const std::string& line);

    std::string port_;
    int baudrate_;
    std::string parser_; // "json" or "csv"
    std::vector<std::string> csv_fields_;

#ifdef _WIN32
    HANDLE port_handle_{INVALID_HANDLE_VALUE};
#else
    int port_fd_{-1};
    struct termios original_termios_;
#endif

    std::atomic<uint64_t> bytes_read_{0};
    std::atomic<uint64_t> parse_errors_{0};
};

} // namespace glinx
