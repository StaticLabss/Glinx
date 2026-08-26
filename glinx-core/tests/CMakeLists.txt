cmake_minimum_required(VERSION 3.20)

# Google Test
include(FetchContent)
FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG v1.14.0
)
FetchContent_MakeAvailable(googletest)

enable_testing()

# Test executables
add_executable(test_buffer test_buffer.cpp)
target_link_libraries(test_buffer 
    PRIVATE 
    glinx_core 
    GTest::gtest_main
)

include(GoogleTest)
gtest_discover_tests(test_buffer)
