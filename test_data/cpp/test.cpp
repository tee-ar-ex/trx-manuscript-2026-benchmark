#include "trx/trx.h"
#include <iostream>

int main(int argc, char** argv) {
    if (argc < 3) return 1;
    trx::AnyTrxFile trx_file = trx::AnyTrxFile::load(argv[1]);
    trx_file.save(argv[2]);
    return 0;
}
