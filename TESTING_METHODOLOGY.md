# Testing Methodology

This document describes the test suites, measurement protocol, and OS cache eviction strategy
used to ensure scientific rigor across all four language implementations.

---

## 1. Measurement Protocol: Cold Start & Cache Eviction

### The Problem: OS Page Cache Contamination

The Linux kernel maintains a **page cache** — a region of RAM that stores recently accessed
disk blocks. After any file read, the kernel keeps the file's blocks in RAM. Subsequent reads
to the same file are served from RAM (~40 GB/s) rather than from storage (~4 GB/s), a
difference of roughly **10×**. If benchmarks do not flush the page cache between iterations,
the results measure RAM throughput, not true disk I/O — a scientifically invalid comparison.

### The Solution: System-wide Cache Eviction (`drop_caches`)

All benchmark runners execute a system call to drop the global OS page cache before **every timed iteration**:

```bash
sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'
```

This instructs the kernel to **release all cached pages** from the page cache across the entire system. The next `read()`, `pread()`, or `mmap()` call will be served from storage rather than RAM, reliably simulating a cold-start scenario.

**Key properties of this approach:**
- Requires root (`sudo`) privileges.
- Forces a complete flush of the global system cache, ensuring pristine benchmark conditions.
- Can be run without a password prompt by configuring the `sudoers` file (see README for instructions).

### Per-Language Implementations

| Language | Code | Location |
|----------|------|----------|
| **Python** | `os.system("sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null")` | `python/utils.py` |
| **Rust** | `Command::new("sh").arg("-c").arg("sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null").status()` | `rust/src/utils.rs` |
| **C++** | `system("sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null")` | `cpp/utils.cpp` |
| **JavaScript** | `execSync("sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null")` | `js/utils.js` |

### Iteration Schema

Each benchmark runner follows this exact timed sequence per iteration:

```
for each iteration i in [0 .. NUM_ITERATIONS]:
    1. evict_all()            ← sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'
    2. t_start = now()
    3. obj = load(file)       ← reads from disk (not cache)
    4. t_end = now()
    5. record (t_end - t_start) as load_time[i]
    6. t_start = now()
    7. save(obj, out_file)
    8. t_end = now()
    9. record (t_end - t_start) as save_time[i]
    10. free(obj)             ← gc.collect() / malloc_trim(0) / drop() / global.gc()
```

- **Iteration 0** (Cold Run): timed, but **excluded** from summary statistics. Incurs OS I/O
  start-up overhead, dynamic linking, and interpreter initialization.
- **Iterations 1–N** (Warm Runs): timed and **included** in the final mean ± std table.
  Because cache is evicted before each, "warm" refers only to amortized linking overhead —
  **not** warm-cache I/O.

---

## 2. Unified Tests (`integrity_tests.py`)

**Purpose:** Validates the static integrity of individual read/write operations per language.

**How it works:** It takes a single Gold Standard file (e.g., `gs.trx` or `gs.trk`), passes
it to a specific language (e.g., C++), saves a new file (`tmp_cpp.trx`), and compares the
spatial coordinates, streamline counts, and offsets against the *original* Gold Standard.

**What it tells us:**
- "Does C++ correctly read a TRX file and save it exactly as it found it?"
- Identifies isolated bugs within a single library's IO implementation.
- Verifies that down-casting, inverse affine transformations, and basic byte-parsing are
  mathematically correct within a closed system.

---

## 3. Relay-Style Tests (`relay_tests.py`)

**Purpose:** Validates cumulative interoperability, cross-ecosystem metadata survival, and
conversion safety over long pipelines.

**How it works:** It cascades the output of one language into the input of the next. For
example, the *Language Relay* passes a file like a baton:
`gs.trx` → Python → Rust → C++ → JavaScript → Final `.trx`. It compares only the final
output to the original.

**What it tells us:**
- **Language Compatibility:** If any library writes a slightly non-standard JSON header or
  misaligned byte, the next library in the chain will fail. It mathematically proves true
  interoperability without isolated quirks.
- **Precision Auditing:** Relays intentionally cast coordinates down (e.g., `float64` →
  `float16` → `float64`) to empirically measure the maximum physical spatial drift (in mm)
  caused by compression.
- **Format Degradation:** Passing coordinates through legacy formats (`TRX → TRK → TCK →
  VTK → TRX`) explicitly exposes which formats cause fatal metadata loss. Historically,
  chaining through `TCK` and `VTK` silently destroyed affine matrices and spatial headers.
  We solved this limitation across all language tracks by dynamically injecting a reference
  NIfTI header (`--ref fa.nii`) during legacy conversion. This allows the parsers to fully
  reconstruct the structural properties before re-serializing into the robust `TRX` format,
  ensuring zero metadata drift.

---

## 4. Compression Tests (`compression_tests.py`)

**Purpose:** Validates that all four language implementations can correctly read and write
**compressed** TRX archives (ZIP DEFLATED), and that data integrity is preserved when a
compressed file is relayed through every language in sequence.

**How it works:** The test proceeds in three phases:

1. **Compress (Python):** The Gold Standard file (`gs_from_py.trx`) is loaded into memory
   and re-saved with `compression_standard=zipfile.ZIP_DEFLATED`, producing a smaller
   compressed archive. The original and compressed sizes are logged.
2. **Cross-language relay:** The compressed file is passed as input to each language in turn
   (`Python → JavaScript → C++ → Rust`). Each language loads the compressed archive and
   saves a new file, which becomes the input for the next language.
3. **Integrity check:** The final output is compared against the original in-memory
   streamlines using `np.allclose(..., atol=1e-4)`. Any coordinate mismatch causes the
   test to abort with a non-zero exit code.

**What it tells us:**
- **Compressed-format interoperability:** Confirms that every library's ZIP parser can
  transparently handle `ZIP_DEFLATED` archives, not just uncompressed (`ZIP_STORED`) ones.
- **Round-trip fidelity under compression:** Guarantees that the deflate/inflate cycle does
  not introduce silent bit corruption or precision loss beyond the `1e-4 mm` tolerance.
- **Production readiness:** Most real-world TRX files shipped in pipelines are compressed;
  this test ensures libraries do not silently fail or produce garbage when encountering them.

---

## 5. Extreme Edge-Case Tests (`extreme_tests.py`)

**Purpose:** Validates the resilience, scalability, and stability of the parsers under extreme
stress, malformed data, and edge-case geometries.

**How it works:** It generates synthetic datasets representing boundary conditions and feeds
them to the parsing libraries across all four languages. The tests include:

- **Empty/Minimal TRX Test:** 0 vertices, 0 streamlines. Ensures the parsers handle empty
  buffers without throwing alignment panics or division-by-zero errors.
- **Extreme Values Relay:** Injects `NaN`, `Inf`, `-Inf`, and absolute maximum bounds for
  integer types to ensure parsers do not overflow or corrupt data structures when saving/loading.
- **Corrupted File Test:** Truncates a TRX zip archive mid-file to guarantee parsers
  gracefully fail rather than crashing the host process.
- **Dictionary Stress Test:** Synthetically generates hundreds of thousands of unique metadata
  dictionary keys to ensure JSON parsers and hash map allocations do not balloon
  uncontrollably.
- **1 GB Scalability & Throughput Test:** Generates a synthetic ~1 GB uncompressed TRX
  (160 M vertices). It clocks the duration and throughput (MB/s) of loading and re-saving the
  dataset to ensure all tracks remain within a stable relative performance window (0.1× to
  10.0× of each other) to prevent unseen performance regressions.

**What it tells us:**
- "Is the library robust enough for production?"
- It confirms that the underlying memory models (e.g., C++ `std::vector`, Rust `Vec`,
  JS `ArrayBuffer`) do not collapse under memory fragmentation or OOM conditions when pushed
  to theoretical limits.
