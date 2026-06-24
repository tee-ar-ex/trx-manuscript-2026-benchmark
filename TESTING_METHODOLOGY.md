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
