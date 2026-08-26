cmake_minimum_required(VERSION 3.20)
project(glinx-core VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Compiler flags for performance
if(MSVC)
    add_compile_options(/W4 /O2 /GL)
    add_link_options(/LTCG)
else()
    add_compile_options(-Wall -Wextra -O3 -march=native -flto)
endif()

# Include directories
include_directories(include)

# Header-only dependencies (add as submodules or fetch)
include(FetchContent)

# nlohmann/json
FetchContent_Declare(
    json
    URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
)
FetchContent_MakeAvailable(json)

# spdlog
FetchContent_Declare(
    spdlog
    GIT_REPOSITORY https://github.com/gabime/spdlog.git
    GIT_TAG v1.13.0
)
set(SPDLOG_USE_STD_FORMAT ON CACHE BOOL "Use std::format in spdlog" FORCE)
FetchContent_MakeAvailable(spdlog)

# readerwriterqueue (lock-free queue)
FetchContent_Declare(
    readerwriterqueue
    GIT_REPOSITORY https://github.com/cameron314/readerwriterqueue.git
    GIT_TAG master
)
FetchContent_MakeAvailable(readerwriterqueue)

# Core library sources
set(CORE_SOURCES
    src/buffer.cpp
    src/driver.cpp
    src/ipc.cpp
    src/profiler.cpp
    src/drivers/serial.cpp
    src/drivers/i2c.cpp
    src/drivers/spi.cpp
    src/drivers/can.cpp
)

# Core library (static)
add_library(glinx_core STATIC ${CORE_SOURCES})
target_include_directories(glinx_core PUBLIC 
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${readerwriterqueue_SOURCE_DIR}
)
target_link_libraries(glinx_core PUBLIC 
    nlohmann_json::nlohmann_json
    spdlog::spdlog
)

# Platform-specific serial port libraries
if(WIN32)
    target_link_libraries(glinx_core PUBLIC setupapi)
elseif(UNIX)
    target_link_libraries(glinx_core PUBLIC pthread)
endif()

# Python bindings (optional, built separately with nanobind)
option(BUILD_PYTHON_BINDINGS "Build Python bindings with nanobind" ON)
if(BUILD_PYTHON_BINDINGS)
    find_package(Python 3.11 COMPONENTS Interpreter Development REQUIRED)
    
    # Nanobind
    FetchContent_Declare(
        nanobind
        GIT_REPOSITORY https://github.com/wjakob/nanobind.git
        GIT_TAG v2.0.0
    )
    FetchContent_MakeAvailable(nanobind)
    
    nanobind_add_module(_glinx_core bindings/python.cpp)
    target_link_libraries(_glinx_core PRIVATE glinx_core)
endif()

# Testing
option(BUILD_TESTS "Build C++ tests" ON)
if(BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

# Benchmarks
option(BUILD_BENCHMARKS "Build benchmarks" ON)
if(BUILD_BENCHMARKS)
    add_subdirectory(benchmarks)
endif()

# Installation
install(TARGETS glinx_core
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)
install(DIRECTORY include/ DESTINATION include)
