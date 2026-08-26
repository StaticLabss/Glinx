#include "glinx/ipc.hpp"
#include "glinx/drivers/serial.hpp"
#include "glinx/drivers/i2c.hpp"
#include "glinx/drivers/spi.hpp"
#include <spdlog/spdlog.h>
#include <cstring>

#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#endif

namespace glinx {

// IPC Manager Implementation
IPCManager::IPCManager(const std::string& shm_name, size_t shm_size)
    : shm_name_(shm_name), shm_size_(shm_size) {
    create_shm();
}

IPCManager::~IPCManager() {
    destroy_shm();
}

bool IPCManager::create_shm() {
#ifdef _WIN32
    shm_handle_ = CreateFileMappingA(
        INVALID_HANDLE_VALUE,
        nullptr,
        PAGE_READWRITE,
        0,
        static_cast<DWORD>(shm_size_),
        shm_name_.c_str()
    );
    
    if (!shm_handle_) {
        spdlog::error("Failed to create shared memory: {}", shm_name_);
        return false;
    }
    
    shm_ptr_ = MapViewOfFile(
        shm_handle_,
        FILE_MAP_ALL_ACCESS,
        0,
        0,
        shm_size_
    );
    
    if (!shm_ptr_) {
        spdlog::error("Failed to map shared memory: {}", shm_name_);
        CloseHandle(shm_handle_);
        shm_handle_ = nullptr;
        return false;
    }
#else
    shm_fd_ = shm_open(shm_name_.c_str(), O_CREAT | O_RDWR, 0666);
    
    if (shm_fd_ < 0) {
        spdlog::error("Failed to create shared memory: {}", shm_name_);
        return false;
    }
    
    if (ftruncate(shm_fd_, shm_size_) < 0) {
        spdlog::error("Failed to set shared memory size");
        ::close(shm_fd_);
        shm_fd_ = -1;
        return false;
    }
    
    shm_ptr_ = mmap(nullptr, shm_size_, PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd_, 0);
    
    if (shm_ptr_ == MAP_FAILED) {
        spdlog::error("Failed to map shared memory");
        ::close(shm_fd_);
        shm_fd_ = -1;
        shm_ptr_ = nullptr;
        return false;
    }
#endif
    
    // Initialize header: [message_count (uint32_t)] [messages...]
    std::memset(shm_ptr_, 0, shm_size_);
    spdlog::info("Created shared memory: {} ({} bytes)", shm_name_, shm_size_);
    return true;
}

void IPCManager::destroy_shm() {
#ifdef _WIN32
    if (shm_ptr_) {
        UnmapViewOfFile(shm_ptr_);
        shm_ptr_ = nullptr;
    }
    if (shm_handle_) {
        CloseHandle(shm_handle_);
        shm_handle_ = nullptr;
    }
#else
    if (shm_ptr_) {
        munmap(shm_ptr_, shm_size_);
        shm_ptr_ = nullptr;
    }
    if (shm_fd_ >= 0) {
        ::close(shm_fd_);
        shm_unlink(shm_name_.c_str());
        shm_fd_ = -1;
    }
#endif
}

size_t IPCManager::write_messages(const std::vector<SensorMessage>& messages) {
    if (!shm_ptr_ || messages.empty()) {
        return 0;
    }
    
    // Calculate space needed
    size_t header_size = sizeof(uint32_t);
    size_t message_size = sizeof(SensorMessage);
    size_t max_messages = (shm_size_ - header_size) / message_size;
    size_t to_write = std::min(messages.size(), max_messages);
    
    // Write count
    uint32_t count = static_cast<uint32_t>(to_write);
    std::memcpy(shm_ptr_, &count, sizeof(count));
    
    // Write messages
    uint8_t* ptr = static_cast<uint8_t*>(shm_ptr_) + header_size;
    for (size_t i = 0; i < to_write; ++i) {
        std::memcpy(ptr, &messages[i], message_size);
        ptr += message_size;
    }
    
    total_written_ += to_write;
    return to_write;
}

// Runtime Implementation
GlinxRuntime::GlinxRuntime(const std::string& config_json) {
    load_config(config_json);
    
    buffer_ = std::make_unique<SensorBuffer>();
    ipc_ = std::make_unique<IPCManager>("glinx_shm");
}

GlinxRuntime::~GlinxRuntime() {
    stop();
}

void GlinxRuntime::load_config(const std::string& config_json) {
    try {
        config_ = json::parse(config_json);
    } catch (const json::parse_error& e) {
        spdlog::error("Failed to parse config: {}", e.what());
        config_ = json::object();
    }
}

void GlinxRuntime::start() {
    if (!config_.contains("sources")) {
        spdlog::warn("No sources configured");
        return;
    }
    
    for (const auto& source : config_["sources"]) {
        DriverConfig driver_config;
        driver_config.source_id = source.value("id", "unknown");
        driver_config.protocol = source.value("protocol", "mock");
        driver_config.options = source.value("options", json::object());
        
        std::unique_ptr<Driver> driver;
        
        if (driver_config.protocol == "serial") {
            driver = std::make_unique<SerialDriver>(driver_config, buffer_.get());
        } else if (driver_config.protocol == "i2c") {
            driver = std::make_unique<I2CDriver>(driver_config, buffer_.get());
        } else if (driver_config.protocol == "spi") {
            driver = std::make_unique<SPIDriver>(driver_config, buffer_.get());
        } else {
            spdlog::warn("Unknown protocol: {}", driver_config.protocol);
            continue;
        }
        
        driver->start();
        drivers_.push_back(std::move(driver));
    }
    
    spdlog::info("Started {} drivers", drivers_.size());
}

void GlinxRuntime::stop() {
    for (auto& driver : drivers_) {
        driver->stop();
    }
    drivers_.clear();
}

std::vector<SensorMessage> GlinxRuntime::get_messages() {
    auto messages = buffer_->drain();
    
    // Also write to shared memory for Python layer
    if (!messages.empty()) {
        ipc_->write_messages(messages);
    }
    
    return messages;
}

json GlinxRuntime::get_stats() const {
    json stats = {
        {"buffer_size", buffer_->size()},
        {"total_pushed", buffer_->total_pushed()},
        {"total_dropped", buffer_->total_dropped()},
        {"ipc_written", ipc_->total_written()},
        {"drivers", json::array()}
    };
    
    for (const auto& driver : drivers_) {
        stats["drivers"].push_back(driver->get_stats());
    }
    
    return stats;
}

} // namespace glinx
