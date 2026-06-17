import sys
import os
from trx.trx_file_memmap import load, save

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    t = load(input_file)
    save(t, output_file)
