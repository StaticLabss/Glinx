#include <gtest/gtest.h>
#include "glinx/buffer.hpp"
#include <thread>
#include <chrono>

using namespace glinx;

TEST(RingBufferTest, BasicPushPop) {
    RingBuffer<int, 8> buffer;
    
    EXPECT_TRUE(buffer.empty());
    EXPECT_EQ(buffer.size(), 0);
    
    EXPECT_TRUE(buffer.push(42));
    EXPECT_FALSE(buffer.empty());
    EXPECT_EQ(buffer.size(), 1);
    
    auto val = buffer.pop();
    ASSERT_TRUE(val.has_value());
    EXPECT_EQ(*val, 42);
    EXPECT_TRUE(buffer.empty());
}

TEST(RingBufferTest, CapacityLimits) {
    RingBuffer<int, 4> buffer;
    
    EXPECT_TRUE(buffer.push(1));
    EXPECT_TRUE(buffer.push(2));
    EXPECT_TRUE(buffer.push(3));
    EXPECT_FALSE(buffer.push(4)); // Buffer full (capacity - 1)
    
    EXPECT_EQ(buffer.size(), 3);
}

TEST(RingBufferTest, DrainAll) {
    RingBuffer<int, 16> buffer;
    
    for (int i = 0; i < 10; ++i) {
        buffer.push(i);
    }
    
    auto items = buffer.drain();
    EXPECT_EQ(items.size(), 10);
    EXPECT_TRUE(buffer.empty());
    
    for (size_t i = 0; i < items.size(); ++i) {
        EXPECT_EQ(items[i], static_cast<int>(i));
    }
}

TEST(RingBufferTest, WrapAround) {
    RingBuffer<int, 4> buffer;
    
    // Fill, drain, repeat
    for (int cycle = 0; cycle < 5; ++cycle) {
        buffer.push(cycle * 10 + 1);
        buffer.push(cycle * 10 + 2);
        buffer.push(cycle * 10 + 3);
        
        auto val1 = buffer.pop();
        auto val2 = buffer.pop();
        auto val3 = buffer.pop();
        
        ASSERT_TRUE(val1.has_value());
        ASSERT_TRUE(val2.has_value());
        ASSERT_TRUE(val3.has_value());
        
        EXPECT_EQ(*val1, cycle * 10 + 1);
        EXPECT_EQ(*val2, cycle * 10 + 2);
        EXPECT_EQ(*val3, cycle * 10 + 3);
    }
}

TEST(SensorBufferTest, BasicOperations) {
    SensorBuffer buffer;
    
    SensorMessage msg;
    std::strncpy(msg.source_id, "test", sizeof(msg.source_id) - 1);
    std::strncpy(msg.protocol, "mock", sizeof(msg.protocol) - 1);
    msg.timestamp = 123.456;
    msg.payload_size = 10;
    
    EXPECT_TRUE(buffer.push(msg));
    EXPECT_EQ(buffer.total_pushed(), 1);
    EXPECT_EQ(buffer.size(), 1);
    
    auto messages = buffer.drain();
    EXPECT_EQ(messages.size(), 1);
    EXPECT_STREQ(messages[0].source_id, "test");
    EXPECT_DOUBLE_EQ(messages[0].timestamp, 123.456);
}

TEST(SensorBufferTest, HighFrequency) {
    SensorBuffer buffer;
    
    SensorMessage msg;
    std::strncpy(msg.source_id, "imu", sizeof(msg.source_id) - 1);
    std::strncpy(msg.protocol, "i2c", sizeof(msg.protocol) - 1);
    
    const size_t count = 10000;
    auto start = std::chrono::high_resolution_clock::now();
    
    for (size_t i = 0; i < count; ++i) {
        msg.timestamp = static_cast<double>(i);
        buffer.push(msg);
    }
    
    auto end = std::chrono::high_resolution_clock::now();
    auto duration_us = std::chrono::duration_cast<std::chrono::microseconds>(end - start).count();
    
    double messages_per_us = count / static_cast<double>(duration_us);
    double messages_per_second = messages_per_us * 1e6;
    
    std::cout << "Pushed " << count << " messages in " << duration_us << " µs\n";
    std::cout << "Throughput: " << messages_per_second << " msgs/sec\n";
    
    EXPECT_GT(messages_per_second, 1000000); // > 1M msgs/sec
}

int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
