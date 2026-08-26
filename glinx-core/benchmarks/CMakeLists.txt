cmake_minimum_required(VERSION 3.20)

add_executable(latency_bench latency_bench.cpp)
target_link_libraries(latency_bench PRIVATE glinx_core)

add_executable(throughput_bench throughput_bench.cpp)
target_link_libraries(throughput_bench PRIVATE glinx_core)
