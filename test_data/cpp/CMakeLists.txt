
cmake_minimum_required(VERSION 3.16)
project(test_cpp CXX)
set(CMAKE_CXX_STANDARD 17)
set(TRX_BUILD_TESTS OFF CACHE BOOL "Build trx tests" FORCE)
set(TRX_BUILD_EXAMPLES OFF CACHE BOOL "Build trx examples" FORCE)
add_subdirectory("/home/local/USHERBROOKE/rhef1902/Libraries/trx/trx-nature-2026-benchmark/../trx-cpp" trx-cpp-build)
add_executable(test_cpp test.cpp)
target_link_libraries(test_cpp PRIVATE trx)
