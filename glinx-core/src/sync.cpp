#include "glinx/sync.hpp"
#include <spdlog/spdlog.h>
#include <algorithm>

namespace glinx {

void SensorSync::add_sensor(const std::string& sensor_id, double max_age_sec) {
    std::lock_guard<std::mutex> lock(mutex_);
    
    SensorState state;
    state.sensor_id = sensor_id;
    state.max_age_sec = max_age_sec;
    state.last_timestamp = 0.0;
    state.has_data = false;
    
    sensors_[sensor_id] = state;
}

void SensorSync::update(const std::string& sensor_id, double timestamp, const json& data) {
    std::lock_guard<std::mutex> lock(mutex_);
    
    auto it = sensors_.find(sensor_id);
    if (it == sensors_.end()) {
        return;
    }
    
    it->second.last_timestamp = timestamp;
    it->second.last_data = data;
    it->second.has_data = true;
}

std::optional<json> SensorSync::get_synchronized_frame(double current_time) {
    std::lock_guard<std::mutex> lock(mutex_);
    
    // Check if all sensors have data
    bool all_have_data = true;
    double oldest_timestamp = current_time;
    
    for (const auto& [id, state] : sensors_) {
        if (!state.has_data) {
            all_have_data = false;
            break;
        }
        
        // Check if data is too old
        double age = current_time - state.last_timestamp;
        if (age > state.max_age_sec) {
            all_have_data = false;
            break;
        }
        
        oldest_timestamp = std::min(oldest_timestamp, state.last_timestamp);
    }
    
    if (!all_have_data) {
        return std::nullopt;
    }
    
    // Build synchronized frame
    json frame;
    frame["timestamp"] = oldest_timestamp;
    frame["sensors"] = json::object();
    
    for (const auto& [id, state] : sensors_) {
        frame["sensors"][id] = state.last_data;
    }
    
    return frame;
}

json SensorSync::get_stats() const {
    std::lock_guard<std::mutex> lock(mutex_);
    
    json stats;
    stats["sensor_count"] = sensors_.size();
    stats["sensors"] = json::array();
    
    for (const auto& [id, state] : sensors_) {
        json sensor_info;
        sensor_info["id"] = id;
        sensor_info["has_data"] = state.has_data;
        sensor_info["last_timestamp"] = state.last_timestamp;
        sensor_info["max_age_sec"] = state.max_age_sec;
        stats["sensors"].push_back(sensor_info);
    }
    
    return stats;
}

} // namespace glinx
