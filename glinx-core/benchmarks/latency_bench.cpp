#include "glinx/buffer.hpp"
#include <iostream>
#include <chrono>
#include <vector>
#include <algorithm>
#include <numeric>

using namespace glinx;
using namespace std::chrono;

int main() {
    const size_t iterations = 100000;
    std::vector<double> latencies;
    latencies.reserve(iterations);

    SensorBuffer buffer;
    SensorMessage msg;
    std::strncpy(msg.source_id, "bench", sizeof(msg.source_id) - 1);
    std::strncpy(msg.protocol, "mock", sizeof(msg.protocol) - 1);
    msg.payload_size = 64;

    std::cout << "=== Glinx Buffer Latency Benchmark ===\n";
    std::cout << "Iterations: " << iterations << "\n\n";

    // Measure push latency
    for (size_t i = 0; i < iterations; ++i) {
        auto start = high_resolution_clock::now();
        buffer.push(msg);
        auto end = high_resolution_clock::now();

        auto latency_ns = duration_cast<nanoseconds>(end - start).count();
        latencies.push_back(static_cast<double>(latency_ns));
    }

    // Calculate statistics
    std::sort(latencies.begin(), latencies.end());
    
    double sum = std::accumulate(latencies.begin(), latencies.end(), 0.0);
    double mean = sum / latencies.size();
    
    double min = latencies.front();
    double p50 = latencies[latencies.size() / 2];
    double p95 = latencies[latencies.size() * 95 / 100];
    double p99 = latencies[latencies.size() * 99 / 100];
    double max = latencies.back();

    std::cout << "Push Latency:\n";
    std::cout << "  Mean: " << mean << " ns\n";
    std::cout << "  Min:  " << min << " ns\n";
    std::cout << "  P50:  " << p50 << " ns\n";
    std::cout << "  P95:  " << p95 << " ns\n";
    std::cout << "  P99:  " << p99 << " ns\n";
    std::cout << "  Max:  " << max << " ns\n";

    // Drain latency
    auto drain_start = high_resolution_clock::now();
    auto messages = buffer.drain();
    auto drain_end = high_resolution_clock::now();
    auto drain_us = duration_cast<microseconds>(drain_end - drain_start).count();

    std::cout << "\nDrain Performance:\n";
    std::cout << "  Messages: " << messages.size() << "\n";
    std::cout << "  Time: " << drain_us << " µs\n";
    std::cout << "  Rate: " << (messages.size() / static_cast<double>(drain_us)) << " M msgs/sec\n";

    // Target check
    std::cout << "\n=== Performance Targets ===\n";
    std::cout << "  Target push latency: < 1000 ns (1 µs)\n";
    std::cout << "  Actual P99: " << p99 << " ns";
    if (p99 < 1000) {
        std::cout << " ✓ PASS\n";
    } else {
        std::cout << " ✗ FAIL\n";
    }

    return (p99 < 1000) ? 0 : 1;
}
