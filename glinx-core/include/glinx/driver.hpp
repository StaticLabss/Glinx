#pragma once

#include "buffer.hpp"
#include <memory>
#include <string>
#include <thread>
#include <atomic>
#include <nlohmann/json.hpp>

namespace glinx {

using json = nlohmann::json;

/**
 * Driver configuration parsed from Python layer.
 */
struct DriverConfig {
    std::string source_id;
    std::string protocol;
    json options;
};

/**
 * Base driver interface for hardware protocols.
 * All drivers run in dedicated threads and push to lock-free buffers.
 */
class Driver {
public:
    explicit Driver(const DriverConfig& config, SensorBuffer* buffer);
    virtual ~Driver();

    // Non-copyable, non-movable
    Driver(const Driver&) = delete;
    Driver& operator=(const Driver&) = delete;

    /**
     * Start the driver thread.
     */
    void start();

    /**
     * Stop the driver thread gracefully.
     */
    void stop();

    /**
     * Check if driver is running.
     */
    bool is_running() const { return running_.load(); }

    /**
     * Get driver statistics.
     */
    virtual json get_stats() const;

protected:
    /**
     * Main poll loop - implemented by each driver.
     * Should check stop_requested() periodically.
     */
    virtual void poll_loop() = 0;

    /**
     * Check if stop has been requested.
     */
    bool stop_requested() const { return stop_flag_.load(); }

    /**
     * Push a message to the buffer.
     */
    bool push_message(const SensorMessage& msg);

    /**
     * Helper to create timestamp.
     */
    static double get_timestamp();

    DriverConfig config_;
    SensorBuffer* buffer_;

private:
    void run();

    std::unique_ptr<std::thread> thread_;
    std::atomic<bool> running_{false};
    std::atomic<bool> stop_flag_{false};
    std::atomic<uint64_t> messages_sent_{0};
    std::atomic<uint64_t> errors_{0};
};

} // namespace glinx
