# Build script for Glinx C++ core on Windows

$ErrorActionPreference = "Stop"

Write-Host "=== Building Glinx C++ Core ===" -ForegroundColor Cyan

# Create build directory
$BUILD_DIR = "glinx-core\build"
if (-not (Test-Path $BUILD_DIR)) {
    New-Item -ItemType Directory -Path $BUILD_DIR | Out-Null
}

Push-Location $BUILD_DIR

try {
    # Configure with CMake
    Write-Host "`nConfiguring with CMake..." -ForegroundColor Yellow
    cmake .. -DCMAKE_BUILD_TYPE=Release -G "Visual Studio 17 2022"
    
    if ($LASTEXITCODE -ne 0) {
        throw "CMake configuration failed"
    }
    
    # Build
    Write-Host "`nBuilding..." -ForegroundColor Yellow
    cmake --build . --config Release
    
    if ($LASTEXITCODE -ne 0) {
        throw "Build failed"
    }
    
    Write-Host "`n✓ Build successful!" -ForegroundColor Green
    Write-Host "`nArtifacts:" -ForegroundColor Cyan
    Write-Host "  - Static library: $BUILD_DIR\Release\glinx_core.lib"
    Write-Host "  - Python module: $BUILD_DIR\Release\_glinx_core.pyd"
    
    # Run tests if requested
    if ($args -contains "--test") {
        Write-Host "`nRunning tests..." -ForegroundColor Yellow
        ctest -C Release --output-on-failure
    }
    
    # Run benchmarks if requested
    if ($args -contains "--bench") {
        Write-Host "`nRunning benchmarks..." -ForegroundColor Yellow
        .\Release\latency_bench.exe
        .\Release\throughput_bench.exe 1000 5
    }
    
} finally {
    Pop-Location
}
