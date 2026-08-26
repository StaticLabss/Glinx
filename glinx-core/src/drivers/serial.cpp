#include "glinx/drivers/serial.hpp"
#include <spdlog/spdlog.h>
#include <nlohmann/json.hpp>
#include <thread>
#include <chrono>

#ifndef _WIN32
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#endif

namespace glinx {

SerialDriver::SerialDriver(const DriverConfig& config, SensorBuffer* buffer)
    : Driver(config, buffer) {
    
    port_ = config_.options.value("port", "");
    baudrate_ = config_.options.value("baudrate", 115200);
    parser_ = config_.options.value("parser", "json");
    
    if (config_.options.contains("csv_fields")) {
        csv_fields_ = config_.options["csv_fields"].get<std::vector<std::string>>();
    }
}

SerialDriver::~SerialDriver() {
    close_port();
}

bool SerialDriver::open_port() {
#ifdef _WIN32
    // Windows serial port
    std::string full_port = "\\\\.\\" + port_;
    port_handle_ = CreateFileA(
        full_port.c_str(),
        GENERIC_READ | GENERIC_WRITE,
        0,
        nullptr,
        OPEN_EXISTING,
        0,
        nullptr
    );
    
    if (port_handle_ == INVALID_HANDLE_VALUE) {
        spdlog::error("Failed to open serial port {}", port_);
        return false;
    }
    
    DCB dcb = {};
    dcb.DCBlength = sizeof(dcb);
    
    if (!GetCommState(port_handle_, &dcb)) {
        spdlog::error("GetCommState failed for {}", port_);
        close_port();
        return false;
    }
    
    dcb.BaudRate = baudrate_;
    dcb.ByteSize = 8;
    dcb.StopBits = ONESTOPBIT;
    dcb.Parity = NOPARITY;
    
    if (!SetCommState(port_handle_, &dcb)) {
        spdlog::error("SetCommState failed for {}", port_);
        close_port();
        return false;
    }
    
    COMMTIMEOUTS timeouts = {};
    timeouts.ReadIntervalTimeout = 50;
    timeouts.ReadTotalTimeoutConstant = 50;
    timeouts.ReadTotalTimeoutMultiplier = 10;
    
    SetCommTimeouts(port_handle_, &timeouts);
    
#else
    // POSIX serial port
    port_fd_ = ::open(port_.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
    
    if (port_fd_ < 0) {
        spdlog::error("Failed to open serial port {}", port_);
        return false;
    }
    
    // Save original termios
    tcgetattr(port_fd_, &original_termios_);
    
    struct termios tty = {};
    if (tcgetattr(port_fd_, &tty) != 0) {
        spdlog::error("tcgetattr failed for {}", port_);
        close_port();
        return false;
    }
    
    // Configure baud rate
    speed_t baud;
    switch (baudrate_) {
        case 9600: baud = B9600; break;
        case 19200: baud = B19200; break;
        case 38400: baud = B38400; break;
        case 57600: baud = B57600; break;
        case 115200: baud = B115200; break;
        case 230400: baud = B230400; break;
        case 460800: baud = B460800; break;
        case 921600: baud = B921600; break;
        default:
            spdlog::warn("Unsupported baud rate {}, using 115200", baudrate_);
            baud = B115200;
    }
    
    cfsetispeed(&tty, baud);
    cfsetospeed(&tty, baud);
    
    // 8N1 mode
    tty.c_cflag &= ~PARENB;
    tty.c_cflag &= ~CSTOPB;
    tty.c_cflag &= ~CSIZE;
    tty.c_cflag |= CS8;
    tty.c_cflag &= ~CRTSCTS;
    tty.c_cflag |= CREAD | CLOCAL;
    
    tty.c_lflag &= ~ICANON;
    tty.c_lflag &= ~ECHO;
    tty.c_lflag &= ~ECHOE;
    tty.c_lflag &= ~ECHONL;
    tty.c_lflag &= ~ISIG;
    
    tty.c_iflag &= ~(IXON | IXOFF | IXANY);
    tty.c_iflag &= ~(IGNBRK | BRKINT | PARMRK | ISTRIP | INLCR | IGNCR | ICRNL);
    
    tty.c_oflag &= ~OPOST;
    tty.c_oflag &= ~ONLCR;
    
    tty.c_cc[VTIME] = 1;
    tty.c_cc[VMIN] = 0;
    
    if (tcsetattr(port_fd_, TCSANOW, &tty) != 0) {
        spdlog::error("tcsetattr failed for {}", port_);
        close_port();
        return false;
    }
#endif
    
    spdlog::info("Opened serial port {} @ {} baud", port_, baudrate_);
    return true;
}

void SerialDriver::close_port() {
#ifdef _WIN32
    if (port_handle_ != INVALID_HANDLE_VALUE) {
        CloseHandle(port_handle_);
        port_handle_ = INVALID_HANDLE_VALUE;
    }
#else
    if (port_fd_ >= 0) {
        tcsetattr(port_fd_, TCSANOW, &original_termios_);
        ::close(port_fd_);
        port_fd_ = -1;
    }
#endif
}

bool SerialDriver::read_line(std::string& line) {
    line.clear();
    char ch;
    
#ifdef _WIN32
    DWORD bytes_read;
    while (!stop_requested()) {
        if (!ReadFile(port_handle_, &ch, 1, &bytes_read, nullptr)) {
            return false;
        }
        
        if (bytes_read == 1) {
            bytes_read_.fetch_add(1);
            if (ch == '\n') {
                return !line.empty();
            }
            if (ch != '\r') {
                line += ch;
            }
        }
    }
#else
    while (!stop_requested()) {
        ssize_t n = ::read(port_fd_, &ch, 1);
        
        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                std::this_thread::sleep_for(std::chrono::microseconds(100));
                continue;
            }
            return false;
        }
        
        if (n == 1) {
            bytes_read_.fetch_add(1);
            if (ch == '\n') {
                return !line.empty();
            }
            if (ch != '\r') {
                line += ch;
            }
        }
    }
#endif
    
    return false;
}

json SerialDriver::parse_line(const std::string& line) {
    if (parser_ == "json") {
        try {
            return json::parse(line);
        } catch (const json::parse_error& e) {
            parse_errors_.fetch_add(1);
            return {{"raw", line}};
        }
    } else if (parser_ == "csv") {
        json result;
        size_t pos = 0, field_idx = 0;
        std::string token;
        
        for (size_t i = 0; i <= line.length(); ++i) {
            if (i == line.length() || line[i] == ',') {
                token = line.substr(pos, i - pos);
                
                std::string field_name = field_idx < csv_fields_.size() 
                    ? csv_fields_[field_idx] 
                    : "field_" + std::to_string(field_idx);
                
                // Try to parse as number
                try {
                    if (token.find('.') != std::string::npos) {
                        result[field_name] = std::stod(token);
                    } else {
                        result[field_name] = std::stoi(token);
                    }
                } catch (...) {
                    result[field_name] = token;
                }
                
                pos = i + 1;
                ++field_idx;
            }
        }
        
        return result;
    }
    
    return {{"raw", line}};
}

void SerialDriver::poll_loop() {
    if (!open_port()) {
        spdlog::error("Failed to open serial port {}", port_);
        return;
    }
    
    std::string line;
    
    while (!stop_requested()) {
        if (read_line(line)) {
            json parsed = parse_line(line);
            
            SensorMessage msg;
            std::strncpy(msg.source_id, config_.source_id.c_str(), sizeof(msg.source_id) - 1);
            std::strncpy(msg.protocol, "serial", sizeof(msg.protocol) - 1);
            msg.timestamp = get_timestamp();
            
            std::string payload_str = parsed.dump();
            msg.payload_size = std::min(payload_str.size(), sizeof(msg.payload));
            std::memcpy(msg.payload, payload_str.data(), msg.payload_size);
            
            push_message(msg);
        }
    }
    
    close_port();
}

json SerialDriver::get_stats() const {
    auto stats = Driver::get_stats();
    stats["bytes_read"] = bytes_read_.load();
    stats["parse_errors"] = parse_errors_.load();
    stats["port"] = port_;
    stats["baudrate"] = baudrate_;
    return stats;
}

} // namespace glinx
