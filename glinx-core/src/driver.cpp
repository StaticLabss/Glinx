#include "glinx/driver.hpp"
#include <spdlog/spdlog.h>
#include <chrono>

namespace glinx {

Driver::Driver(const DriverConfig& config, SensorBuffer* buffer)
    : config_(config), buffer_(buffer) {}

Driver::~Driver() {
    if (running_.load()) {
        stop();
    }
}

void Driver::start() {
    if (running_.load()) {
        spdlog::warn("Driver {} already running", config_.source_id);
        return;
    }

    stop_flag_.store(false);
    thread_ = std::make_unique<std::thread>(&Driver::run, this);
    spdlog::info("Started driver: {} ({})", config_.source_id, config_.protocol);
}

void Driver::stop() {
    if (!running_.load()) {
        return;
    }

    spdlog::info("Stopping driver: {}", config_.source_id);
    stop_flag_.store(true);
    
    if (thread_ && thread_->joinable()) {
        thread_->join();
    }
    
    running_.store(false);
    spdlog::info("Stopped driver: {}", config_.source_id);
}

void Driver::run() {
    running_.store(true);
    
    try {
        poll_loop();
    } catch (const std::exception& e) {
        spdlog::error("Driver {} crashed: {}", config_.source_id, e.what());
        errors_.fetch_add(1);
    }
    
    running_.store(false);
}

bool Driver::push_message(const SensorMessage& msg) {
    if (buffer_->push(msg)) {
        messages_sent_.fetch_add(1);
        return true;
    }
    
    errors_.fetch_add(1);
    return false;
}

double Driver::get_timestamp() {
    using namespace std::chrono;
    return duration<double>(system_clock::now().time_since_epoch()).count();
}

json Driver::get_stats() const {
    return {
        {"source_id", config_.source_id},
        {"protocol", config_.protocol},
        {"running", running_.load()},
        {"messages_sent", messages_sent_.load()},
        {"errors", errors_.load()}
    };
}

} // namespace glinx
