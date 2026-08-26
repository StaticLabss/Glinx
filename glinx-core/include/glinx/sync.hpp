#pragma once

#include <string>
#include <unordered_map>
#include <mutex>
#include <optional>
#include <nlohmann/json.hpp>

namespace glinx {

using json = nlohmann::json;

/**
 * Multi-sensor synchronization for time-aligned data frames.
 * Useful for robotics applications requiring coordinated sensor fusion.
 */
class SensorSync {
public:
    /**
     * Add a sensor to the synchronization group.
     */
    void add_sensor(const std::string& sensor_id, double max_age_sec = 0.1);
    
    /**
     * Update sensor data.
     */
    void update(const std::string& sensor_id, double timestamp, const json& data);
    
    /**
     * Get synchronized frame if all sensors have recent data.
     * Returns std::nullopt if any sensor is missing or stale.
     */
    std::optional<json> get_synchronized_frame(double current_time);
    
    /**
     * Get synchronization statistics.
     */
    json get_stats() const;

private:
    struct SensorState {
        std::string sensor_id;
        double last_timestamp;
        json last_data;
        double max_age_sec;
        bool has_data;
    };
    
    mutable std::mutex mutex_;
    std::unordered_map<std::string, SensorState> sensors_;
};

} // namespace glinx
