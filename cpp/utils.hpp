#ifndef UTILS_HPP
#define UTILS_HPP

#include <string>
#include <trx/legacy_io.h>

void evict_from_cache(const std::string &filename);
void release_memory();

#endif // UTILS_HPP
