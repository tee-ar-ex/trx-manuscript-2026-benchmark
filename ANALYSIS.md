# TRX Benchmark Suite Analysis & Interpretation Guide

This document provides a comprehensive breakdown of the benchmark suite's expectations, known failure cases, language-specific behaviors, and hardware recommendations. It is intended to guide researchers and developers in interpreting the output of the multi-language tractography benchmark.

---

## 1. Expected Normal Behavior

*   **Dynamic Baseline Scaling**: The orchestrator is designed to run completely blind to the initial dataset size. It dynamically records the streamline and point counts of the *first successfully loaded file* and establishes it as the truth. Therefore, it is entirely normal to swap between a tiny 10k streamline dataset and a 90GB production dataset without modifying any code.
*   **Cold vs. Warm Runs**: 
    *   The `[COLD RUN]` (Iteration 0) is expected to be substantially slower (often 10x to 100x slower). This is because the OS kernel must physically fetch the file blocks from the SSD/HDD into the page cache.
    *   `[WARM RUNS]` (Iterations 1-10) represent raw parsing performance. Because the runners use programmatic OS cache eviction (`posix_fadvise`) between iterations, the files are always read from disk. However, dynamic linking overhead and language interpreter startup costs are amortized, making warm runs slightly faster and significantly more stable than the cold run.

---

## 2. Expected Failure Cases & Unreadable Files

You will observe `[ERROR] Loading failed` for specific files during the benchmark. **These are expected failures** that highlight feature disparity across the language ecosystems:

| File Pattern | Failing Language(s) | Reason for Failure |
| :--- | :--- | :--- |
| `*ui64_w_metadata.trx` | **C++**, **JavaScript** | **64-bit Metadata Parsing:** These files contain *metadata* (per-vertex scalars or per-streamline properties) stored as 64-bit integers (`int64`). <br><br>👉 **C++**: The `trx-cpp` static library is strictly typed and throws an `Unsupported group dtype` exception to prevent data truncation.<br>👉 **JavaScript**: The V8 engine's WebGL-compatible `TypedArray` system lacks native 64-bit integer arrays. The JS reader throws an overflow error to protect data integrity. |
| `*.trk` (with properties) | **Rust** (Strict mode) | **Strict Type Safety:** The `trx-rs` crate intentionally drops/panics on `.trk` files containing scalars to prevent silent data loss during conversion. *(Note: Our benchmark implements a custom `.trk` bypass parser in Rust to get around this for timing purposes).* |

---

## 3. Typical Behavior & Duration Ratios (X vs. Y)

The benchmark highlights drastic architectural differences between legacy formats and the new TRX standard.

### The Memory-Mapping Advantage (Python)
*   **TRX loading in Python is virtually instantaneous (e.g., 0.001s).**
*   **Why?** The TRX format is designed around memory-mapping (`mmap`). Python's `trx-python` implementation defers the actual loading of data. We force the information to memory and like other languages we force-cast it to float32. Legacy formats (TRK/TCK) require sequentially scanning the entire 5GB file byte-by-byte into memory.

### The Raw Power of C++ and Rust
*   **C++ and Rust dominate legacy parsing.**
*   **Why?** Parsing `.vtk` and `.trk` requires reading millions of sequential coordinates, unpacking them, and byteswapping them (handling Endianness). C++ and Rust compile this into heavily optimized, vectorized machine code.
*   **Ratio:** C++ and Rust can parse legacy TRK/VTK files **10x to 15x faster** than Python's `nibabel` library.

### JavaScript Overhead
*   **JavaScript is consistently the slowest (up to 3x slower than Python).**
*   **Why?** V8's single-threaded nature and garbage collection struggle with massive contiguous memory blocks. Reading a 4GB file requires allocating ArrayBuffers, unzipping them (`fflate`), and casting them into `Float32Arrays`, which triggers massive GC pauses.

---

## 4. Limitations in Interpretation

When analyzing the `summary.md` table, keep the following caveats in mind:

1.  **Unfair comparisons?**: It is extremely difficult to have fair comparisons across languages, this is only a showcase of current code, not a statement about potential/hypothetical speed limit. 
2.  **No Rendering Metrics**: This benchmark measures strictly **I/O File Parsing** (Disk to RAM). It does not measure the time taken to upload buffers to a GPU or draw the tractogram on a screen.
3.  **Language Ecosystem Constraints**: The C++ and Rust legacy parsers were custom-written for this benchmark specifically to achieve maximum raw throughput. Python relies on the general-purpose `nibabel` library, which incurs heavy object-oriented overhead (e.g., creating `ArraySequence` objects) that inflates its load times.

---

## 5. Recommended Hardware

To achieve reproducible and accurate results on the massive (5.9M+ streamline) dataset, the following hardware is strongly recommended:

*   **Storage (Critical)**: **PCIe Gen 4.0 NVMe SSD** (e.g., Samsung 980 Pro, WD Black SN850). If you run this on a mechanical HDD or network drive, the disk IOPS bottleneck will completely mask the parsing differences between C++ and Python.
*   **RAM**: Minimum **32 GB DDR4/DDR5**. Parsing the 8GB uncompressed files requires at least double the file size in memory for temporary decompression buffers, especially in JavaScript.
*   **CPU**: Modern multi-core CPU (e.g., Ryzen 5000+ or Intel 12th Gen+) with high single-thread clock speeds, as unzipping `.trx` files is primarily a single-threaded bottleneck.
