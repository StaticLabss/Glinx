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
    add_compile_definitions(NOMINMAX WIN32_LEAN_AND_MEAN)
else()
    add_compile_options(-Wall -Wextra -O3 -flto)
    # Native CPU instructions are useful for local benchmarks but make
    # binary wheels unsafe to distribute to other machines.
    if(NOT SKBUILD)
        add_compile_options(-march=native)
    endif()
endif()

# Include directories
include_directories(include)

# Header-only dependencies (add as submodules or fetch)
include(FetchContent)

# nlohmann/json
FetchContent_Declare(
    json
    URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
FetchContent_MakeAvailable(json)

# spdlog
# NOTE: SPDLOG_USE_STD_FORMAT is intentionally left OFF. spdlog's bundled
# fmt formatter is fully header-only and portable, whereas libc++'s
# std::format floating-point support only became available at runtime on
# macOS 13.3+, which broke wheels built with an older deployment target.
FetchContent_Declare(
    spdlog
    GIT_REPOSITORY https://github.com/gabime/spdlog.git
    GIT_TAG v1.15.3
)
set(SPDLOG_USE_STD_FORMAT OFF CACHE BOOL "Use std::format in spdlog" FORCE)
set(SPDLOG_FMT_EXTERNAL OFF CACHE BOOL "Use external fmt library" FORCE)
FetchContent_MakeAvailable(spdlog)

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
set_target_properties(glinx_core PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_include_directories(glinx_core PUBLIC 
    ${CMAKE_CURRENT_SOURCE_DIR}/include
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
    if(NOT APPLE)
        # POSIX shm_open/shm_unlink live in librt on glibc (including the
        # manylinux images used for wheel builds). Without this, the
        # extension fails to import at runtime with an undefined symbol
        # error once loaded outside of a build tree that happens to have
        # librt already pulled in transitively.
        find_library(GLINX_RT_LIBRARY rt)
        if(GLINX_RT_LIBRARY)
            target_link_libraries(glinx_core PUBLIC ${GLINX_RT_LIBRARY})
        endif()
    endif()
endif()

# Python bindings (optional, built separately with nanobind)
option(BUILD_PYTHON_BINDINGS "Build Python bindings with nanobind" ON)
if(BUILD_PYTHON_BINDINGS)
    find_package(Python 3.11 COMPONENTS Interpreter Development.Module REQUIRED)
    
    # Nanobind
    FetchContent_Declare(
        nanobind
        GIT_REPOSITORY https://github.com/wjakob/nanobind.git
        GIT_TAG v2.0.0
    )
    FetchContent_MakeAvailable(nanobind)
    
    nanobind_add_module(_glinx_core bindings/python.cpp)
    target_link_libraries(_glinx_core PRIVATE glinx_core)
    install(TARGETS _glinx_core
        LIBRARY DESTINATION glinx
        RUNTIME DESTINATION glinx
    )
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
if(NOT SKBUILD)
    install(TARGETS glinx_core
        LIBRARY DESTINATION lib
        ARCHIVE DESTINATION lib
    )
    install(DIRECTORY include/ DESTINATION include)
endif()
