cmake_minimum_required(VERSION 3.16)
project(test_cpp CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(TRX_BUILD_TESTS OFF CACHE BOOL "Build trx tests" FORCE)
set(TRX_BUILD_EXAMPLES OFF CACHE BOOL "Build trx examples" FORCE)
set(TRX_BUILD_BENCHMARKS OFF CACHE BOOL "Build trx benchmarks" FORCE)
add_subdirectory("/home/local/USHERBROOKE/rhef1902/Libraries/trx/trx-nature-2026-benchmark/../trx-cpp" trx-cpp-build)
add_executable(test_cpp
    test.cpp
    /home/local/USHERBROOKE/rhef1902/Libraries/trx/trx-nature-2026-benchmark/cpp/utils.cpp
)
target_include_directories(test_cpp PRIVATE /home/local/USHERBROOKE/rhef1902/Libraries/trx/trx-nature-2026-benchmark/cpp)
target_link_libraries(test_cpp PRIVATE trx)
find_package(Threads REQUIRED)
target_link_libraries(test_cpp PRIVATE Threads::Threads)
