#include "glinx/ipc.hpp"
#include "glinx/driver.hpp"
#include "glinx/drivers/serial.hpp"
#include "glinx/drivers/i2c.hpp"
#include "glinx/drivers/spi.hpp"
#include <spdlog/spdlog.h>

#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#endif

namespace glinx {

// ──────────────────────────────────────────────────────────────
// IPCManager Implementation
// ──────────────────────────────────────────────────────────────

IPCManager::IPCManager(const std::string& shm_name, size_t shm_size)
    : shm_name_(shm_name), shm_size_(shm_size) {
    
    if (!create_shm()) {
        spdlog::error("Failed to create shared memory '{}'", shm_name_);
    }
}

IPCManager::~IPCManager() {
    destroy_shm();
}

bool IPCManager::create_shm() {
#ifdef _WIN32
    // Windows: Create named file mapping
    shm_handle_ = CreateFileMappingA(
        INVALID_HANDLE_VALUE,
        nullptr,
        PAGE_READWRITE,
        0,
        static_cast<DWORD>(shm_size_),
        shm_name_.c_str()
    );
    
    if (shm_handle_ == nullptr) {
        spdlog::error("Failed to create file mapping: {}", GetLastError());
        return false;
    }
    
    shm_ptr_ = MapViewOfFile(
        shm_handle_,
        FILE_MAP_ALL_ACCESS,
        0,
        0,
        shm_size_
    );
    
    if (shm_ptr_ == nullptr) {
        spdlog::error("Failed to map view of file: {}", GetLastError());
        CloseHandle(shm_handle_);
        shm_handle_ = nullptr;
        return false;
    }
    
#else
    // Linux/macOS: POSIX shared memory
    shm_fd_ = shm_open(shm_name_.c_str(), O_CREAT | O_RDWR, 0666);
    
    if (shm_fd_ < 0) {
        spdlog::error("Failed to create shared memory: {}", strerror(errno));
        return false;
    }
    
    if (ftruncate(shm_fd_, shm_size_) < 0) {
        spdlog::error("Failed to set shared memory size: {}", strerror(errno));
        close(shm_fd_);
        shm_unlink(shm_name_.c_str());
        shm_fd_ = -1;
        return false;
    }
    
    shm_ptr_ = mmap(nullptr, shm_size_, PROT_READ | PROT_WRITE, 
                    MAP_SHARED, shm_fd_, 0);
    
    if (shm_ptr_ == MAP_FAILED) {
        spdlog::error("Failed to map shared memory: {}", strerror(errno));
        close(shm_fd_);
        shm_unlink(shm_name_.c_str());
        shm_fd_ = -1;
        shm_ptr_ = nullptr;
        return false;
    }
#endif
    
    spdlog::info("Created shared memory '{}' ({} bytes)", shm_name_, shm_size_);
    return true;
}

void IPCManager::destroy_shm() {
#ifdef _WIN32
    if (shm_ptr_ != nullptr) {
        UnmapViewOfFile(shm_ptr_);
        shm_ptr_ = nullptr;
    }
    
    if (shm_handle_ != nullptr) {
        CloseHandle(shm_handle_);
        shm_handle_ = nullptr;
    }
    
#else
    if (shm_ptr_ != nullptr && shm_ptr_ != MAP_FAILED) {
        munmap(shm_ptr_, shm_size_);
        shm_ptr_ = nullptr;
    }
    
    if (shm_fd_ >= 0) {
        close(shm_fd_);
        shm_unlink(shm_name_.c_str());
        shm_fd_ = -1;
    }
#endif
}

size_t IPCManager::write_messages(const std::vector<SensorMessage>& messages) {
    if (shm_ptr_ == nullptr || messages.empty()) {
        return 0;
    }
    
    // Simple ring buffer protocol:
    // [uint32_t count][message1][message2]...
    // Python layer reads and clears
    
    uint32_t* count_ptr = static_cast<uint32_t*>(shm_ptr_);
    char* data_ptr = static_cast<char*>(shm_ptr_) + sizeof(uint32_t);
    
    size_t available = shm_size_ - sizeof(uint32_t);
    size_t written = 0;
    
    for (const auto& msg : messages) {
        if (available < sizeof(SensorMessage)) {
            break;
        }
        
        std::memcpy(data_ptr, &msg, sizeof(SensorMessage));
        data_ptr += sizeof(SensorMessage);
        available -= sizeof(SensorMessage);
        written++;
    }
    
    *count_ptr = written;
    total_written_ += written;
    
    return written;
}

// ──────────────────────────────────────────────────────────────
// GlinxRuntime Implementation
// ──────────────────────────────────────────────────────────────

GlinxRuntime::GlinxRuntime(const std::string& config_json) {
    load_config(config_json);
    
    buffer_ = std::make_unique<SensorBuffer>(16384);
    ipc_ = std::make_unique<IPCManager>("glinx_shm", 65536);
}

GlinxRuntime::~GlinxRuntime() {
    stop();
}

void GlinxRuntime::load_config(const std::string& config_json) {
    try {
        config_ = json::parse(config_json);
    } catch (const json::parse_error& e) {
        spdlog::error("Failed to parse config JSON: {}", e.what());
        config_ = json::object();
    }
}

void GlinxRuntime::start() {
    if (!config_.contains("sources") || !config_["sources"].is_array()) {
        spdlog::warn("No sources configured");
        return;
    }
    
    for (const auto& source_cfg : config_["sources"]) {
        DriverConfig driver_cfg;
        driver_cfg.source_id = source_cfg.value("id", "unknown");
        driver_cfg.protocol = source_cfg.value("protocol", "mock");
        driver_cfg.options = source_cfg.value("options", json::object());
        
        std::unique_ptr<Driver> driver;
        
        if (driver_cfg.protocol == "serial") {
            driver = std::make_unique<SerialDriver>(driver_cfg, buffer_.get());
        } else if (driver_cfg.protocol == "i2c") {
            driver = std::make_unique<I2CDriver>(driver_cfg, buffer_.get());
        } else if (driver_cfg.protocol == "spi") {
            driver = std::make_unique<SPIDriver>(driver_cfg, buffer_.get());
        } else {
            spdlog::warn("Unknown protocol '{}' for source '{}'", 
                        driver_cfg.protocol, driver_cfg.source_id);
            continue;
        }
        
        driver->start();
        drivers_.push_back(std::move(driver));
        
        spdlog::info("Started driver for source '{}' (protocol: {})", 
                    driver_cfg.source_id, driver_cfg.protocol);
    }
    
    spdlog::info("Glinx runtime started with {} drivers", drivers_.size());
}

void GlinxRuntime::stop() {
    for (auto& driver : drivers_) {
        driver->stop();
    }
    drivers_.clear();
    spdlog::info("Glinx runtime stopped");
}

std::vector<SensorMessage> GlinxRuntime::get_messages() {
    auto messages = buffer_->drain();
    
    // Also write to shared memory for Python layer
    if (ipc_) {
        ipc_->write_messages(messages);
    }
    
    return messages;
}

json GlinxRuntime::get_stats() const {
    json stats = json::object();
    
    stats["buffer_size"] = buffer_->size();
    stats["buffer_pushed"] = buffer_->total_pushed();
    stats["buffer_dropped"] = buffer_->total_dropped();
    
    if (ipc_) {
        stats["ipc_written"] = ipc_->total_written();
    }
    
    json driver_stats = json::array();
    for (const auto& driver : drivers_) {
        driver_stats.push_back(driver->get_stats());
    }
    stats["drivers"] = driver_stats;
    
    return stats;
}

} // namespace glinx
