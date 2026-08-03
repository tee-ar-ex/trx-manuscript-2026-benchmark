# Relay vs. Unified Testing

### Unified Tests (`unified_test.py`)
**Purpose:** Validates the static integrity of individual read/write operations per language.
**How it works:** It takes a single Gold Standard file (e.g., `gs.trx` or `gs.trk`), passes it to a specific language (e.g., C++), saves a new file (`tmp_cpp.trx`), and compares the spatial coordinates, streamline counts, and offsets against the *original* Gold Standard.
**What it tells us:** 
- "Does C++ correctly read a TRX file and save it exactly as it found it?"
- Identifies isolated bugs within a single library's IO implementation.
- Verifies that down-casting, inverse affine transformations, and basic byte-parsing are mathematically correct within a closed system.

### Relay-Style Tests (`relay_test.py`)
**Purpose:** Validates cumulative interoperability, cross-ecosystem metadata survival, and conversion safety over long pipelines.
**How it works:** It cascades the output of one language into the input of the next. For example, the *Language Relay* passes a file like a baton: `gs.trx` -> Python -> Rust -> C++ -> JavaScript -> Final `.trx`. It compares only the final output to the original.
**What it tells us:**
- **Language Compatibility:** If any library writes a slightly non-standard JSON header or misaligned byte, the next library in the chain will fail. It mathematically proves true interoperability without isolated quirks.
- **Precision Auditing:** Relays intentionally cast coordinates down (e.g., `float64` -> `float16` -> `float64`) to empirically measure the maximum physical spatial drift (in mm) caused by compression.
- **Format Degradation:** Passing coordinates through legacy formats (`TRX -> TRK -> TCK -> VTK -> TRX`) explicitly exposes which formats cause fatal metadata loss. Historically, chaining through `TCK` and `VTK` silently destroyed affine matrices and spatial headers. We solved this limitation across all language tracks by dynamically injecting a reference NIfTI header (`--ref fa.nii`) during legacy conversion. This allows the parsers to fully reconstruct the structural properties before re-serializing into the robust `TRX` format, ensuring zero metadata drift.

### Extreme Edge-Case Tests (`extreme_tests.py`)
**Purpose:** Validates the resilience, scalability, and stability of the parsers under extreme stress, malformed data, and edge-case geometries.
**How it works:** It generates synthetic datasets representing boundary conditions and feeds them to the parsing libraries across all four languages. The tests include:
- **Empty/Minimal TRX Test:** 0 vertices, 0 streamlines. Ensures the parsers handle empty buffers without throwing alignment panics or division-by-zero errors.
- **Extreme Values Relay:** Injects `NaN`, `Inf`, `-Inf`, and absolute maximum bounds for integer types to ensure parsers do not overflow or corrupt data structures when saving/loading.
- **Corrupted File Test:** Truncates a TRX zip archive mid-file to guarantee parsers gracefully fail rather than crashing the host process.
- **Dictionary Stress Test:** Synthetically generates hundreds of thousands of unique metadata dictionary keys to ensure JSON parsers and hash map allocations do not balloon uncontrollably.
- **1GB Scalability & Throughput Test:** Generates a synthetic ~1GB uncompressed TRX (160M vertices). It clocks the duration and throughput (MB/s) of loading and re-saving the dataset to ensure all tracks remain within a stable relative performance window (0.1x to 10.0x of each other) to prevent unseen performance regressions.
**What it tells us:**
- "Is the library robust enough for production?"
- It confirms that the underlying memory models (e.g., C++ `std::vector`, Rust `Vec`, JS `ArrayBuffer`) do not collapse under memory fragmentation or OOM conditions when pushed to theoretical limits.
