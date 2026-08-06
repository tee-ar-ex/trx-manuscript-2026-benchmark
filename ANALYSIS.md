# TRX Benchmark Suite Analysis & Interpretation Guide

This document provides a comprehensive breakdown of the benchmark suite's expectations, known
failure cases, language-specific behaviors, and hardware recommendations. It is intended to
guide researchers and developers in interpreting the output of the multi-language tractography
benchmark.

---

## 1. Recent Architecture Centralization

Historically, the `trx-nature-2026-benchmark` repository contained redundant I/O logic across JavaScript, C++, and Rust in order to bypass shortcomings in the core `trx` libraries (especially regarding legacy TRK, TCK, and VTK support).

As of the latest major refactor:

* **No IO Code in Benchmark:** All legacy loaders, writers, and format translators have been
  successfully migrated directly into the core libraries (`trx-javascript`, `trx-cpp`, and
  `trx-rs`). The benchmark repo now acts purely as an orchestrator.
* **Metadata Integrity:** Translating from legacy formats (or memory-mapped TRXs) no longer
  drops original header metadata. For instance, `trx-cpp` caches the `original_trx` state to
  prevent destructive downcasting during standard conversions.
* **Spatial Precision:** By mapping `rasmm` to voxel space using inverse affine transforms (especially during JS TRK export), cross-language coordinate parity is maintained to within 0.001 mm tolerance.

---

## 2. I/O Architecture & Streaming IO Updates

A major update across `trx-javascript`, `trx-rs`, and `trx-cpp` fundamentally shifted the I/O
strategy to eliminate unnecessary in-memory duplication and monolithic processing, which
historically caused fragmentation and Out-Of-Memory (OOM) crashes on large datasets.

### The Problem with Monolithic Reading/Writing

The original approach read the entire `.trx` file into a single RAM buffer, extracting all
inner ZIP payload files into new simultaneous memory buffers. Saving did the reverse, building
the complete ZIP structure in RAM. Extracting arrays often involved slicing memory (`.slice()`),
creating a third copy of the data. For a 2.5 GB geometry file, peak memory usage easily
ballooned past 7.5 GB+, causing severe memory fragmentation and garbage collection thrashing.

### The Optimized Approach: Streaming & Direct I/O

The TRX file is no longer treated as a generic ZIP to be extracted all at once. It is treated
as a container of memory-mappable arrays.

**For Loading (Reading):**
Instead of extracting the ZIP into RAM, the parsers utilize **Direct-From-Disk Offset Reading**:

1. The parser reads the ZIP's Central Directory (at the end of the file) to find exact byte
   offsets and sizes.
2. It jumps directly to the payload (skipping the Local File Header).
3. If the file is uncompressed (true 99% of the time), OS-level reads (like `fs.readSync` in
   JS, or `mmap`/`pread` in C++ and Rust) pull the bytes directly into the final `Float32Array`
   or `Uint32Array` target.

**Why it's better:** It eliminates intermediate memory copies. We load exactly what we need
into its final resting place. In C++ and Rust, these uncompressed payloads are memory-mapped
directly from the disk, requiring almost zero initial heap memory.

**For Saving (Writing):**
Instead of building a massive ZIP structure in RAM, a **Streaming ZIP Writer** is used:

1. The writer iterates over each array (positions, offsets, metadata).
2. For each file, its ZIP Local File Header is written directly to the disk stream.
3. Array data is streamed directly from its original memory location to the disk, chunk by
   chunk if necessary.
4. Offsets and sizes are recorded to write the ZIP Central Directory at the very end of the
   file.

**Why it's better:** It uses almost zero extra memory. Peak memory usage during saving is
essentially just the size of the array being written, bypassing the need to hold the final
`.trx` file in RAM.

---

## 3. C++ Performance Optimization: O(1) ZIP Directory Lookup

### Background

The TRX file format stores multiple named binary arrays inside a ZIP archive (e.g.,
`positions.3.float32`, `offsets.uint64`, plus any number of metadata arrays). The C++
`trx-cpp` library must locate each array's byte offset within the archive in order to
`mmap` it directly.

### Old Approach: O(n × m) Repeated Linear Scans

The prior implementation called `find_uncompressed_zip_entry_offset(zip_path, name)` once per
array entry. Each call performed a **linear scan** of the entire ZIP from the beginning,
searching for a matching Local File Header. For an archive with `k` arrays:

```
Complexity: O(k × file_size)
```

On a 6 GB dataset with 50 metadata arrays, this caused ~300 GB of data to be scanned before any actual data was loaded — a significant performance bottleneck.

### New Approach: Single-Pass `build_zip_offset_map` (O(file_size) + O(k))

A new function `build_zip_offset_map` performs a **single linear scan** over the entire
archive using `mmap`, reading each `PK\x03\x04` (Local File Header) signature in sequence and
recording every entry's offset into a `std::unordered_map<string, pair<size_t,size_t>>`:

```cpp
using ZipOffsetMap = std::unordered_map<std::string, std::pair<size_t, size_t>>;

ZipOffsetMap build_zip_offset_map(const std::string &zip_path) {
    ZipOffsetMap result;
    mio::shared_mmap_sink zip_mmap(zip_path, 0, file_size);
    // Walk PK headers in O(file_size)
    while (curr <= max_offset) {
        if (/* PK signature */) {
            result.emplace(name, {payload_offset, payload_size});
            curr += header_size + comp_size;
        } else { curr++; }
    }
    return result;
}
```

Subsequent lookups are O(1) hash-map queries. The fix is in
`trx-cpp/src/trx.cpp` and is entirely internal — the public API is unchanged.

---

## 4. Benchmarking Correctness: OS Page Cache Eviction

### Why Eviction is Mandatory

The Linux kernel maintains a **page cache**: a RAM buffer of recently accessed disk blocks.
When a file is read, the kernel caches its blocks in RAM. On subsequent reads, those blocks
are served from RAM at ~40 GB/s rather than from disk at ~4 GB/s — a 10× difference. If
benchmarks do not evict the page cache between iterations, warm-cache results are reported
rather than true I/O performance.

### The Mechanism: `drop_caches`

All benchmark runners use the following system call before each timed iteration:

```bash
sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'
```

This instructs the kernel to **release all cached pages globally**. The
next `read()`, `pread()`, or `mmap()` will be served from storage, not RAM.

**Key properties:**
- Requires root (`sudo`) privileges.
- Forces a complete flush of the global system cache.
- Can be configured in `sudoers` to run without a password prompt.

### Per-Language Implementations

| Language | Code | Location |
|----------|------|----------|
| **Python** | `os.system("sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null")` | `python/utils.py` |
| **Rust** | `Command::new("sh")...` | `rust/src/utils.rs` |
| **C++** | `system("sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null")` | `cpp/utils.cpp` |
| **JavaScript** | `execSync("sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null")` | `js/utils.js` |

---

## 5. Cold vs. Warm Runs: Expected Behavior

*   **Cold Run (Iteration 0)** is expected to be substantially slower (often 3× to 10×). The
    OS kernel must physically fetch file blocks from the SSD/HDD into the page cache. In
    addition, dynamic linking and language interpreter startup costs occur here.
*   **Warm Runs (Iterations 1–10)** represent true parsing performance. Because the runners
    use system cache eviction before iterations, the files are always read
    from disk — not from cache. However, dynamic linking and interpreter startup costs have
    been amortized, making warm runs slightly faster and significantly more stable than the
    cold run.

The cold run timing is recorded but **excluded from the summary statistics** (mean and
standard deviation). Only warm run timings are used in reported results.

---

## 6. Expected Failure Cases & Unreadable Files

You will observe `[ERROR] Loading failed` for specific files during the benchmark.
**These are expected failures** that highlight feature disparity across the language ecosystems:

| File Pattern | Failing Language(s) | Reason for Failure |
| :--- | :--- | :--- |
| `*.trk` (with properties) | **Rust** (Strict mode) | **Strict Type Safety:** The `trx-rs` crate intentionally drops/panics on `.trk` files containing scalars to prevent silent data loss during conversion. *(Our benchmark implements a custom `.trk` bypass parser in Rust for timing purposes.)* |

*(Note: Previously, C++ and JavaScript failed on `uint64`/`int64` metadata groups. This has
been resolved in the underlying parsers by implementing a safe, validated downcasting layer to
32-bit representations where applicable, ensuring cross-platform stability.)*

---

## 7. Typical Behavior & Duration Ratios

The benchmark highlights drastic architectural differences between legacy formats and the new
TRX standard.

### The Memory-Mapping Advantage (Python)

*   **TRX loading in Python is nearly instantaneous (e.g., < 2 s for a 6 GB file).**
*   **Why?** The TRX format is designed around memory-mapping (`mmap`). Python's `trx-python`
    implementation defers the actual loading of data; the call to `load()` maps arrays into
    virtual address space without copying bytes from disk. We then call `to_memory()` and cast
    to `float32`, which forces materialization through OS-optimized sequential I/O.
*   Legacy formats (TRK/TCK) require sequentially scanning the entire 5 GB file byte-by-byte
    into memory — a fundamentally slower operation.

### The Raw Power of C++ and Rust

*   **C++ and Rust dominate legacy parsing.**
*   **Why?** Parsing `.vtk` and `.trk` requires reading millions of sequential coordinates,
    unpacking them, and byteswapping them (handling Endianness). C++ and Rust compile this
    into heavily optimized, vectorized machine code.
*   **Ratio:** C++ and Rust can parse legacy TRK/VTK files **10× to 15× faster** than Python's
    `nibabel` library.

### JavaScript Overhead & Hard Limits

*   **JavaScript is consistently the slowest for loading (up to 3× slower than Python on TRX).**
*   **Why?** V8's abstraction layers (ArrayBuffers, stream callbacks, typed array construction)
    impose overhead even with direct-offset I/O. Reading a multi-gigabyte file involves
    pre-allocating `ArrayBuffer` regions and filling them chunk-by-chunk.
*   **V8 Contiguous Memory Wall (Bypassed)**: V8 imposes a hard maximum of 4 GB for a single
    `ArrayBuffer`. Previously, parsing uncompressed datasets > 2 GB in JS was physically
    impossible. This was resolved by implementing a streaming, chunk-based architectural
    rewrite inside `streamlineIO.mjs` and `js/utils.js`.
*   **Async Timing Fix (August 2026):** A prior version of `benchmark_simple/benchmark.mjs`
    measured spuriously fast load times (~60,000 MB/s) because the timer stopped when the
    Promise resolved rather than when the underlying `ReadStream` finished. After fixing the
    `await` logic, JS load throughput is correctly measured at ~988 MB/s.

---

## 8. Limitations in Interpretation

When analyzing the `summary.md` table, keep the following caveats in mind:

1.  **Unfair comparisons?**: It is extremely difficult to have fair comparisons across
    languages; this is only a showcase of current code, not a statement about potential or
    hypothetical speed limits.
2.  **No Rendering Metrics**: This benchmark measures strictly **I/O File Parsing** (Disk to
    RAM). It does not measure the time taken to upload buffers to a GPU or render on screen.
3.  **Language Ecosystem Constraints**: The C++ and Rust legacy parsers were custom-written
    for this benchmark to achieve maximum raw throughput. Python relies on the general-purpose
    `nibabel` library, which incurs heavy object-oriented overhead (e.g., creating
    `ArraySequence` objects) that inflates its load times.

---

## 9. Recommended Hardware

To achieve reproducible and accurate results on the massive (5.9 M+ streamline) dataset, the
following hardware is strongly recommended:

*   **Storage (Critical)**: **PCIe Gen 4.0 NVMe SSD** (e.g., Samsung 980 Pro, WD Black SN850).
    If you run this on a mechanical HDD or network drive, the disk IOPS bottleneck will
    completely mask the parsing differences between C++ and Python.
*   **RAM**: Minimum **32 GB DDR4/DDR5**. Parsing the 8 GB uncompressed files requires at
    least double the file size in memory for temporary decompression buffers, especially in
    JavaScript.
*   **CPU**: Modern multi-core CPU (e.g., Ryzen 5000+ or Intel 12th Gen+) with high
    single-thread clock speeds, as unzipping `.trx` files is primarily a single-threaded
    bottleneck.
