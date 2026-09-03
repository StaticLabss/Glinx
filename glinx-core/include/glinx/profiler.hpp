#pragma once

#include <chrono>
#include <string>
#include <atomic>
#include <mutex>
#include <unordered_map>
#include <nlohmann/json.hpp>

namespace glinx {

using json = nlohmann::json;
using Clock = std::chrono::high_resolution_clock;
using TimePoint = std::chrono::time_point<Clock>;
using Duration = std::chrono::nanoseconds;

/**
 * Performance profiler for tracking operation latencies and throughput.
 * Thread-safe and low-overhead.
 */
class Profiler {
public:
    struct Stats {
        uint64_t count;
        uint64_t total_ns;
        uint64_t min_ns;
        uint64_t max_ns;
        
        double mean_ns() const {
            return count > 0 ? static_cast<double>(total_ns) / count : 0.0;
        }
        
        json to_json() const {
            return {
                {"count", count},
                {"total_ns", total_ns},
                {"mean_ns", mean_ns()},
                {"min_ns", min_ns},
                {"max_ns", max_ns}
            };
        }
    };
    
    /**
     * RAII timer for automatic profiling.
     */
    class ScopedTimer {
    public:
        ScopedTimer(Profiler& profiler, const std::string& name)
            : profiler_(profiler), name_(name), start_(Clock::now()) {}
        
        ~ScopedTimer() {
            auto end = Clock::now();
            auto duration = std::chrono::duration_cast<Duration>(end - start_);
            profiler_.record(name_, duration.count());
        }
    
    private:
        Profiler& profiler_;
        std::string name_;
        TimePoint start_;
    };
    
    Profiler() = default;
    
    /**
     * Record a measurement.
     */
    void record(const std::string& name, uint64_t duration_ns);
    
    /**
     * Get statistics for a specific operation.
     */
    Stats get_stats(const std::string& name) const;
    
    /**
     * Get all statistics.
     */
    json get_all_stats() const;
    
    /**
     * Reset all statistics.
     */
    void reset();
    
    /**
     * Create a scoped timer.
     */
    ScopedTimer time(const std::string& name) {
        return ScopedTimer(*this, name);
    }

private:
    mutable std::mutex mutex_;
    std::unordered_map<std::string, Stats> stats_;
};

/**
 * Global profiler instance.
 */
extern Profiler g_profiler;

/**
 * Macro for easy profiling.
 */
#define GLINX_PROFILE(name) auto _timer = glinx::g_profiler.time(name)

} // namespace glinx
