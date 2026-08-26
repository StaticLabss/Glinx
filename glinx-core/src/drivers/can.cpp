#include "glinx/drivers/can.hpp"
#include <spdlog/spdlog.h>
#include <thread>
#include <chrono>

#ifndef _WIN32
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#endif

namespace glinx {

CANDriver::CANDriver(const DriverConfig& config, SensorBuffer* buffer)
    : Driver(config, buffer) {
    
    interface_ = config_.options.value("interface", "can0");
    bitrate_ = config_.options.value("bitrate", 500000);  // 500 kbps default
    protocol_ = config_.options.value("protocol", "raw");
    
    if (config_.options.contains("filter_ids")) {
        filter_ids_ = config_.options["filter_ids"].get<std::vector<uint32_t>>();
    }
}

CANDriver::~CANDriver() {
    close_can();
}

bool CANDriver::open_can() {
#ifdef _WIN32
    spdlog::error("CAN driver not supported on Windows");
    return false;
#else
    // Create socket
    socket_fd_ = socket(PF_CAN, SOCK_RAW, CAN_RAW);
    if (socket_fd_ < 0) {
        spdlog::error("Failed to create CAN socket");
        return false;
    }
    
    // Get interface index
    struct ifreq ifr;
    std::strncpy(ifr.ifr_name, interface_.c_str(), IFNAMSIZ - 1);
    
    if (ioctl(socket_fd_, SIOCGIFINDEX, &ifr) < 0) {
        spdlog::error("Failed to get CAN interface index for {}", interface_);
        ::close(socket_fd_);
        socket_fd_ = -1;
        return false;
    }
    
    // Bind socket
    struct sockaddr_can addr;
    addr.can_family = AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;
    
    if (bind(socket_fd_, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        spdlog::error("Failed to bind CAN socket");
        ::close(socket_fd_);
        socket_fd_ = -1;
        return false;
    }
    
    // Set filters
    if (!set_filters()) {
        spdlog::warn("Failed to set CAN filters, receiving all frames");
    }
    
    // Set non-blocking
    int flags = fcntl(socket_fd_, F_GETFL, 0);
    fcntl(socket_fd_, F_SETFL, flags | O_NONBLOCK);
    
    spdlog::info("Opened CAN interface {} @ {} bps", interface_, bitrate_);
    return true;
#endif
}

void CANDriver::close_can() {
#ifndef _WIN32
    if (socket_fd_ >= 0) {
        ::close(socket_fd_);
        socket_fd_ = -1;
    }
#endif
}

bool CANDriver::set_filters() {
#ifdef _WIN32
    return false;
#else
    if (filter_ids_.empty()) {
        return true;  // No filters = accept all
    }
    
    std::vector<struct can_filter> filters;
    for (uint32_t id : filter_ids_) {
        struct can_filter f;
        f.can_id = id;
        f.can_mask = CAN_SFF_MASK;  // Standard frame mask
        filters.push_back(f);
    }
    
    if (setsockopt(socket_fd_, SOL_CAN_RAW, CAN_RAW_FILTER,
                   filters.data(), filters.size() * sizeof(struct can_filter)) < 0) {
        return false;
    }
    
    spdlog::info("Set {} CAN filters", filters.size());
    return true;
#endif
}

json CANDriver::parse_can_frame(uint32_t can_id, const uint8_t* data, size_t len) {
    json result;
    result["can_id"] = can_id;
    result["dlc"] = len;
    
    // Protocol-specific parsing
    if (protocol_ == "obd2" && len >= 2) {
        uint8_t mode = data[0];
        uint8_t pid = data[1];
        return parse_obd2(mode, pid, data + 2, len - 2);
    }
    else if (protocol_ == "j1939") {
        // J1939 parsing (heavy vehicle CAN)
        uint32_t pgn = (can_id >> 8) & 0x1FFFF;
        result["pgn"] = pgn;
        result["priority"] = (can_id >> 26) & 0x7;
        result["source_address"] = can_id & 0xFF;
    }
    
    // Raw data as bytes
    for (size_t i = 0; i < len; ++i) {
        result["data_" + std::to_string(i)] = data[i];
    }
    
    return result;
}

json CANDriver::parse_obd2(uint8_t mode, uint8_t pid, const uint8_t* data, size_t len) {
    json result;
    result["obd2_mode"] = mode;
    result["obd2_pid"] = pid;
    
    if (mode == OBD2::MODE_CURRENT_DATA && len >= 2) {
        switch (pid) {
            case OBD2::PID_ENGINE_RPM:
                result["engine_rpm"] = ((data[0] * 256) + data[1]) / 4.0;
                break;
            
            case OBD2::PID_VEHICLE_SPEED:
                result["vehicle_speed_kph"] = data[0];
                break;
            
            case OBD2::PID_ENGINE_COOLANT_TEMP:
                result["coolant_temperature_c"] = data[0] - 40;
                break;
            
            case OBD2::PID_THROTTLE_POS:
                result["throttle_position_pct"] = (data[0] * 100) / 255.0;
                break;
            
            case OBD2::PID_FUEL_PRESSURE:
                result["fuel_pressure_kpa"] = data[0] * 3;
                break;
            
            case OBD2::PID_INTAKE_MANIFOLD_PRESSURE:
                result["intake_pressure_kpa"] = data[0];
                break;
            
            default:
                // Unknown PID, store raw
                for (size_t i = 0; i < len; ++i) {
                    result["data_" + std::to_string(i)] = data[i];
                }
        }
    }
    
    return result;
}

void CANDriver::poll_loop() {
    if (!open_can()) {
        return;
    }
    
#ifndef _WIN32
    struct can_frame frame;
    
    while (!stop_requested()) {
        ssize_t nbytes = ::read(socket_fd_, &frame, sizeof(frame));
        
        if (nbytes < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                std::this_thread::sleep_for(std::chrono::microseconds(100));
                continue;
            }
            can_errors_.fetch_add(1);
            continue;
        }
        
        if (nbytes == sizeof(frame)) {
            frames_received_.fetch_add(1);
            
            json parsed = parse_can_frame(frame.can_id, frame.data, frame.can_dlc);
            
            SensorMessage msg;
            std::strncpy(msg.source_id, config_.source_id.c_str(), sizeof(msg.source_id) - 1);
            std::strncpy(msg.protocol, "can", sizeof(msg.protocol) - 1);
            msg.timestamp = get_timestamp();
            
            std::string payload_str = parsed.dump();
            msg.payload_size = std::min(payload_str.size(), sizeof(msg.payload));
            std::memcpy(msg.payload, payload_str.data(), msg.payload_size);
            
            push_message(msg);
        }
    }
#endif
    
    close_can();
}

json CANDriver::get_stats() const {
    auto stats = Driver::get_stats();
    stats["interface"] = interface_;
    stats["bitrate"] = bitrate_;
    stats["protocol"] = protocol_;
    stats["frames_received"] = frames_received_.load();
    stats["can_errors"] = can_errors_.load();
    return stats;
}

} // namespace glinx
