#include "glinx/buffer.hpp"

namespace glinx {

SensorBuffer::SensorBuffer(size_t capacity) 
    : buffer_(std::make_unique<RingBuffer<SensorMessage, 16384>>()) {
    // Note: capacity parameter ignored for now, using compile-time constant
}

bool SensorBuffer::push(const SensorMessage& msg) {
    total_pushed_.fetch_add(1, std::memory_order_relaxed);
    
    if (!buffer_->push(msg)) {
        total_dropped_.fetch_add(1, std::memory_order_relaxed);
        return false;
    }
    
    return true;
}

std::vector<SensorMessage> SensorBuffer::drain() {
    return buffer_->drain();
}

size_t SensorBuffer::size() const {
    return buffer_->size();
}

bool SensorBuffer::empty() const {
    return buffer_->empty();
}

} // namespace glinx
