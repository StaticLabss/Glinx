#include "glinx/buffer.hpp"
#include <iostream>
#include <chrono>
#include <thread>
#include <atomic>

using namespace glinx;
using namespace std::chrono;

std::atomic<bool> running{true};
std::atomic<uint64_t> produced{0};
std::atomic<uint64_t> consumed{0};

void producer(SensorBuffer* buffer, size_t messages_per_sec) {
    SensorMessage msg;
    std::strncpy(msg.source_id, "accel", sizeof(msg.source_id) - 1);
    std::strncpy(msg.protocol, "i2c", sizeof(msg.protocol) - 1);
    msg.payload_size = 12; // 3 x 4-byte floats

    auto interval = duration<double>(1.0 / messages_per_sec);
    auto next_send = high_resolution_clock::now();

    while (running.load()) {
        msg.timestamp = duration<double>(high_resolution_clock::now().time_since_epoch()).count();
        
        if (buffer->push(msg)) {
            produced.fetch_add(1);
        }

        next_send += interval;
        std::this_thread::sleep_until(next_send);
    }
}

void consumer(SensorBuffer* buffer) {
    while (running.load() || !buffer->empty()) {
        auto messages = buffer->drain();
        consumed.fetch_add(messages.size());
        
        if (messages.empty()) {
            std::this_thread::sleep_for(milliseconds(1));
        }
    }
}

int main(int argc, char* argv[]) {
    size_t target_rate = 1000; // 1 kHz default
    size_t duration_sec = 5;

    if (argc > 1) {
        target_rate = std::stoull(argv[1]);
    }
    if (argc > 2) {
        duration_sec = std::stoull(argv[2]);
    }

    std::cout << "=== Glinx Throughput Benchmark ===\n";
    std::cout << "Target rate: " << target_rate << " msgs/sec\n";
    std::cout << "Duration: " << duration_sec << " seconds\n\n";

    SensorBuffer buffer;

    // Start threads
    std::thread prod_thread(producer, &buffer, target_rate);
    std::thread cons_thread(consumer, &buffer);

    auto start = high_resolution_clock::now();

    // Run for specified duration
    std::this_thread::sleep_for(seconds(duration_sec));
    running.store(false);

    // Wait for threads
    prod_thread.join();
    cons_thread.join();

    auto end = high_resolution_clock::now();
    auto elapsed_sec = duration<double>(end - start).count();

    // Results
    uint64_t total_produced = produced.load();
    uint64_t total_consumed = consumed.load();
    uint64_t dropped = buffer.total_dropped();

    double actual_rate = total_produced / elapsed_sec;
    double consume_rate = total_consumed / elapsed_sec;
    double loss_rate = (dropped / static_cast<double>(total_produced)) * 100.0;

    std::cout << "=== Results ===\n";
    std::cout << "Produced: " << total_produced << " messages\n";
    std::cout << "Consumed: " << total_consumed << " messages\n";
    std::cout << "Dropped: " << dropped << " messages (" << loss_rate << "%)\n";
    std::cout << "Actual production rate: " << actual_rate << " msgs/sec\n";
    std::cout << "Consumption rate: " << consume_rate << " msgs/sec\n";
    std::cout << "Buffer efficiency: " << ((total_consumed / static_cast<double>(total_produced)) * 100.0) << "%\n";

    std::cout << "\n=== Performance Targets ===\n";
    std::cout << "Target: 10,000 msgs/sec sustained\n";
    std::cout << "Actual: " << actual_rate << " msgs/sec ";
    
    if (actual_rate >= 10000 && loss_rate < 1.0) {
        std::cout << "✓ PASS\n";
        return 0;
    } else {
        std::cout << "✗ FAIL\n";
        return 1;
    }
}
