cmake_minimum_required(VERSION 3.16)
project(trx_benchmark CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Force Release build with -O3
set(CMAKE_BUILD_TYPE Release)
set(CMAKE_CXX_FLAGS_RELEASE "-O3")

# Include trx-cpp subdirectory
set(TRX_BUILD_TESTS OFF CACHE BOOL "Build trx tests" FORCE)
set(TRX_BUILD_EXAMPLES OFF CACHE BOOL "Build trx examples" FORCE)
set(TRX_BUILD_BENCHMARKS OFF CACHE BOOL "Build trx benchmarks" FORCE)

add_subdirectory(../../trx-cpp trx-cpp-build)

# Add our benchmark executable
add_executable(trx_benchmark
    benchmark.cpp
    utils.cpp
    utils.hpp
)

# Link with trx target
target_link_libraries(trx_benchmark PRIVATE trx)

# Find and link threads
find_package(Threads REQUIRED)
target_link_libraries(trx_benchmark PRIVATE Threads::Threads)
