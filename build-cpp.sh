#!/bin/bash
# Build script for Glinx C++ core on Linux/macOS

set -e

echo "=== Building Glinx C++ Core ==="

BUILD_DIR="glinx-core/build"
mkdir -p "$BUILD_DIR"

cd "$BUILD_DIR"

# Configure
echo ""
echo "Configuring with CMake..."
cmake .. -DCMAKE_BUILD_TYPE=Release

# Build
echo ""
echo "Building..."
cmake --build . -j$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

echo ""
echo "✓ Build successful!"
echo ""
echo "Artifacts:"
echo "  - Static library: $BUILD_DIR/libglinx_core.a"
echo "  - Python module: $BUILD_DIR/_glinx_core.so"

# Run tests
if [[ "$*" == *"--test"* ]]; then
    echo ""
    echo "Running tests..."
    ctest --output-on-failure
fi

# Run benchmarks
if [[ "$*" == *"--bench"* ]]; then
    echo ""
    echo "Running benchmarks..."
    ./latency_bench
    ./throughput_bench 1000 5
fi

cd ../..
