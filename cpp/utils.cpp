#include "utils.hpp"
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <malloc.h>
#include <iostream>
#include <thread>
#include <chrono>

void evict_from_cache(const std::string &filename) {
    int ret = system("sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null");
    if (ret != 0) {
        std::cerr << "      [WARN] Cache eviction failed." << std::endl;
    }
}

void release_memory() {
    malloc_trim(0);
}
