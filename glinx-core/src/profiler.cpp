#include "glinx/profiler.hpp"
#include <limits>

namespace glinx {

// Global profiler instance
Profiler g_profiler;

void Profiler::record(const std::string& name, uint64_t duration_ns) {
    std::lock_guard<std::mutex> lock(mutex_);
    
    auto& stats = stats_[name];
    
    if (stats.count == 0) {
        stats.min_ns = std::numeric_limits<uint64_t>::max();
        stats.max_ns = 0;
    }
    
    stats.count++;
    stats.total_ns += duration_ns;
    stats.min_ns = std::min(stats.min_ns, duration_ns);
    stats.max_ns = std::max(stats.max_ns, duration_ns);
}

Profiler::Stats Profiler::get_stats(const std::string& name) const {
    std::lock_guard<std::mutex> lock(mutex_);
    
    auto it = stats_.find(name);
    if (it != stats_.end()) {
        return it->second;
    }
    
    return Stats{0, 0, 0, 0};
}

json Profiler::get_all_stats() const {
    std::lock_guard<std::mutex> lock(mutex_);
    
    json result;
    for (const auto& [name, stats] : stats_) {
        result[name] = stats.to_json();
    }
    
    return result;
}

void Profiler::reset() {
    std::lock_guard<std::mutex> lock(mutex_);
    stats_.clear();
}

} // namespace glinx
