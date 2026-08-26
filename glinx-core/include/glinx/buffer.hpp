#pragma once

#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstring>
#include <memory>
#include <optional>
#include <vector>

namespace glinx {

/**
 * Lock-free ring buffer for single-producer, single-consumer scenarios.
 * Optimized for high-frequency sensor data with zero heap allocations in hot path.
 */
template <typename T, size_t Capacity>
class RingBuffer {
public:
    RingBuffer() : head_(0), tail_(0) {}

    // Non-copyable, non-movable
    RingBuffer(const RingBuffer&) = delete;
    RingBuffer& operator=(const RingBuffer&) = delete;

    /**
     * Push an item to the buffer (producer side).
     * Returns false if buffer is full.
     */
    bool push(const T& item) {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);
        const size_t next_tail = increment(current_tail);
        
        if (next_tail == head_.load(std::memory_order_acquire)) {
            return false; // Buffer full
        }
        
        buffer_[current_tail] = item;
        tail_.store(next_tail, std::memory_order_release);
        return true;
    }

    /**
     * Push with move semantics.
     */
    bool push(T&& item) {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);
        const size_t next_tail = increment(current_tail);
        
        if (next_tail == head_.load(std::memory_order_acquire)) {
            return false;
        }
        
        buffer_[current_tail] = std::move(item);
        tail_.store(next_tail, std::memory_order_release);
        return true;
    }

    /**
     * Pop an item from the buffer (consumer side).
     * Returns std::nullopt if buffer is empty.
     */
    std::optional<T> pop() {
        const size_t current_head = head_.load(std::memory_order_relaxed);
        
        if (current_head == tail_.load(std::memory_order_acquire)) {
            return std::nullopt; // Buffer empty
        }
        
        T item = std::move(buffer_[current_head]);
        head_.store(increment(current_head), std::memory_order_release);
        return item;
    }

    /**
     * Drain all items into a vector (consumer side).
     */
    std::vector<T> drain() {
        std::vector<T> items;
        items.reserve(size());
        
        while (auto item = pop()) {
            items.push_back(std::move(*item));
        }
        
        return items;
    }

    /**
     * Check if buffer is empty.
     */
    bool empty() const {
        return head_.load(std::memory_order_acquire) == 
               tail_.load(std::memory_order_acquire);
    }

    /**
     * Get approximate size (may be stale).
     */
    size_t size() const {
        const size_t h = head_.load(std::memory_order_acquire);
        const size_t t = tail_.load(std::memory_order_acquire);
        return t >= h ? (t - h) : (Capacity - h + t);
    }

    /**
     * Get buffer capacity.
     */
    static constexpr size_t capacity() { return Capacity; }

private:
    static constexpr size_t increment(size_t idx) {
        return (idx + 1) % Capacity;
    }

    alignas(64) std::atomic<size_t> head_; // Cache line alignment
    alignas(64) std::atomic<size_t> tail_;
    T buffer_[Capacity];
};

/**
 * Sensor message structure for C++ layer.
 * Designed to be memcpy-safe and Python-compatible.
 */
struct SensorMessage {
    char source_id[64];
    char protocol[32];
    double timestamp;
    uint8_t payload[512];
    uint32_t payload_size;
    
    SensorMessage() : timestamp(0.0), payload_size(0) {
        std::memset(source_id, 0, sizeof(source_id));
        std::memset(protocol, 0, sizeof(protocol));
        std::memset(payload, 0, sizeof(payload));
    }
};

/**
 * High-frequency sensor buffer with statistics.
 */
class SensorBuffer {
public:
    explicit SensorBuffer(size_t capacity = 16384);
    
    bool push(const SensorMessage& msg);
    std::vector<SensorMessage> drain();
    
    // Statistics
    uint64_t total_pushed() const { return total_pushed_.load(); }
    uint64_t total_dropped() const { return total_dropped_.load(); }
    size_t size() const;
    bool empty() const;

private:
    std::unique_ptr<RingBuffer<SensorMessage, 16384>> buffer_;
    std::atomic<uint64_t> total_pushed_{0};
    std::atomic<uint64_t> total_dropped_{0};
};

} // namespace glinx
