#pragma once

#include "buffer.hpp"
#include <memory>
#include <string>

namespace glinx {

/**
 * Inter-process communication manager.
 * Provides shared memory access for Python layer to read sensor data.
 */
class IPCManager {
public:
    explicit IPCManager(const std::string& shm_name, size_t shm_size = 65536);
    ~IPCManager();

    // Non-copyable, non-movable
    IPCManager(const IPCManager&) = delete;
    IPCManager& operator=(const IPCManager&) = delete;

    /**
     * Write messages to shared memory.
     * Returns number of messages written.
     */
    size_t write_messages(const std::vector<SensorMessage>& messages);

    /**
     * Get shared memory name for Python layer.
     */
    const std::string& shm_name() const { return shm_name_; }

    /**
     * Get statistics.
     */
    uint64_t total_written() const { return total_written_; }

private:
    bool create_shm();
    void destroy_shm();

    std::string shm_name_;
    size_t shm_size_;
    void* shm_ptr_{nullptr};
    uint64_t total_written_{0};

#ifdef _WIN32
    void* shm_handle_{nullptr};
#else
    int shm_fd_{-1};
#endif
};

/**
 * Runtime coordinator for all C++ drivers.
 */
class GlinxRuntime {
public:
    explicit GlinxRuntime(const std::string& config_json);
    ~GlinxRuntime();

    /**
     * Start all configured drivers.
     */
    void start();

    /**
     * Stop all drivers gracefully.
     */
    void stop();

    /**
     * Get messages from buffer (for Python layer).
     */
    std::vector<SensorMessage> get_messages();

    /**
     * Get runtime statistics.
     */
    json get_stats() const;

private:
    void load_config(const std::string& config_json);

    std::unique_ptr<SensorBuffer> buffer_;
    std::vector<std::unique_ptr<Driver>> drivers_;
    std::unique_ptr<IPCManager> ipc_;
    json config_;
};

} // namespace glinx
