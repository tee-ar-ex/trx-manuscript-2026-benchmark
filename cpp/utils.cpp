#include "utils.hpp"
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <malloc.h>
#include <iostream>
#include <thread>
#include <chrono>

void evict_from_cache(const std::string &filename) {
    int fd = open(filename.c_str(), O_RDONLY);
    if (fd < 0) {
        std::cerr << "      [WARN] Cache eviction failed to open file: " << filename << std::endl;
        return;
    }
    struct stat st;
    if (fstat(fd, &st) == 0) {
        if (posix_fadvise(fd, 0, st.st_size, POSIX_FADV_DONTNEED) != 0) {
            std::cerr << "      [WARN] Cache eviction failed (posix_fadvise error) for: " << filename << std::endl;
        }
    }
    close(fd);
    std::this_thread::sleep_for(std::chrono::seconds(1));
}

void release_memory() {
    malloc_trim(0);
    std::this_thread::sleep_for(std::chrono::seconds(1));
}
