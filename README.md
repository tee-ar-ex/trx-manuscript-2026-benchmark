# AI Usage Disclosure

This benchmark suite was developed with the assistance of artificial intelligence, building upon existing implementations and datasets. Below is a detailed breakdown of the source materials, baseline datasets, and the specific tasks delegated to the AI pipeline.

## 📚 Source Materials & Context

The AI agents were provided with the following existing codebases and context to inform the implementation:

**Core TRX Implementations:**
* [`trx-python`](https://github.com/tee-ar-ex/trx-python)
* [`trx-rs`](https://github.com/tee-ar-ex/trx-rs)
* [`trx-cpp`](https://github.com/tee-ar-ex/trx-cpp)
* [`trx-javascript`](https://github.com/tee-ar-ex/trx-javascript)
* [`trx-spec`](https://github.com/tee-ar-ex/trx-spec)

**Additional Context & Libraries:**
* [`vibrant`](https://github.com/as-the-crow-flies/vibrant)
* [`niivue`](https://github.com/niivue/niivue)
* Rust crate: [`trk-io`](https://crates.io/crates/trk-io)
* Rust crate: [`vtkio`](https://docs.rs/vtkio/latest/vtkio/index.html)

---

## 💾 Baseline Datasets

A comprehensive Python benchmark (loading and saving) utilizing a nearly 90GB dataset had already been fully tested prior to the AI's involvement. The dataset files include:

| Size | Filename |
|---|---|
| 5,673,840 | `f32_w_metadata.trk` |
| 2,384,936 | `f32_wo_metadata.trk` |
| 2,431,648 | `f32.tck` |
| 3,982,676 | `f32_ui32_wo_metadata.vtk` |
| 5,418,652 | `f32_ui64_w_metadata.vtk` |
| 3,982,676 | `f32_ui64_wo_metadata.vtk` |
| 6,344,248 | `f64_ui32_wo_metadata.vtk` |
| 7,780,224 | `f64_ui64_w_metadata.vtk` |
| 6,344,248 | `f64_ui64_wo_metadata.vtk` |
| 2,246,644 | `f16_ui32_w_metadata.trx` |
| 1,204,148 | `f16_ui32_wo_metadata.trx` |
| 2,270,000 | `f16_ui64_w_metadata.trx` |
| 1,204,148 | `f16_ui64_wo_metadata.trx` |
| 3,427,428 | `f32_ui32_w_metadata.trx` |
| 2,384,936 | `f32_ui32_wo_metadata.trx` |
| 3,450,784 | `f32_ui64_w_metadata.trx` |
| 2,384,936 | `f32_ui64_wo_metadata.trx` |
| 5,789,004 | `f64_ui32_w_metadata.trx` |
| 4,769,868 | `f64_ui32_wo_metadata.trx` |
| 5,812,360 | `f64_ui64_w_metadata.trx` |
| 4,769,868 | `f64_ui64_wo_metadata.trx` |

---

## 🤖 AI Execution Pipeline

From these existing codebases, the Python datasets, and the established baseline benchmark, an extension task was initiated. The goal was to build a unified, multi-language tractography loading and saving benchmark suite comparing the **TRX (Tractography eXchange)** format against legacy formats (**TRK**, **TCK**, and **VTK**) under various configurations (coordinate precisions, indexing, and metadata structures).

This task was delegated to **Gemini**. Utilizing the Antigravity-CLI alongside the Conductor plugin (Gemini 3.5 Pro), various subagents (Gemini 3.5 Flash) were dispatched to achieve the following:

* **Codebase Mapping:** Analyze and map the provided source repositories.
* **Environment Setup:** Configure the required environments for Python, C++, Rust, and JavaScript.
* **Compilation:** Build the respective environments across all four languages.
* **Benchmark Replication:** Mimic the established Python benchmark logic across the C++, Rust, and JavaScript implementations.
* **Validation:** Perform tests and dry-run validations to ensure parity.
* **Orchestration:** Write wrapper scripts to automate the build, benchmark, and reporting processes.
* **Documentation:** Draft the foundational documentation for the benchmark suite.

> **Note on Verification:** All code generated, results obtained, and reports compiled by the AI pipeline were (or will be) verified by the developer in charge of each respective language implementation.

---

## 📖 Scientific Context & Rationale

Tractography reconstructions of human brains routinely generate datasets containing millions of 3D curves representing white matter fiber pathways (referred to as **streamlines**).

Legacy neuroimaging formats suffer from substantial limitations:

* **TRK (TrackVis)**: A rigid binary format consisting of a fixed 1000-byte header followed by sequential float32 streamline points. It lacks compression, has no support for custom coordinate precisions, and cannot store per-streamline or per-point metadata without changing the file structure.
* **TCK (MRtrix)**: A text header followed by a sequence of binary float32 point coordinates. Streamlines are separated by `NaN` value triplets rather than length indicators. While faster to read than text, the lack of an offset index makes random access impossible and sequential loading slower than memory-mapped arrays.
* **VTK**: General-purpose mesh/polydata format. Because it is designed for arbitrary computer graphics meshes rather than fiber tracts, parsing cell connections adds significant overhead. Modern VTK XML files (`.vtp`) use cell offsets of size `num_cells + 1` (a fence-post representation), adding offset alignment complexity, while legacy `.vtk` files rely on sequential point counting.

### The TRX Solution

The **TRX** format (designed as a hierarchical binary folder structure or zipped archive) addresses these shortcomings:

1. **Memory-Mapping (`mmap`)**: Instead of parsing files sequentially and loading them entirely into memory, TRX maps the raw binary arrays (geometry `positions` and streamline `offsets`) directly into the process's virtual address space.
2. **Configurable Precision**: Coordinate data can be stored in `float16` (half precision), `float32`, or `float64`. Index offsets can be `uint32` or `uint64`. Using `float16` coordinates cuts geometry file sizes in half (e.g., from 4.8 GB down to 2.4 GB) with negligible anatomical precision loss.
3. **Flexible Metadata**: Stores arbitrary per-streamline, per-point, and folder-level metadata in independent array files without rewriting streamline geometry.

This benchmark rigorously evaluates the performance gains achieved by TRX's memory-mapped layout compared to traditional sequential file parsing.

---

## ⚙️ Benchmark Protocol & Design

To ensure scientific rigor and parity across all languages, the benchmarking modules follow a strict measurement protocol:

1. **Single Dataset Directory**: All language runners look for input datasets in the folder specified by the `TRX_BENCHMARK_DATA_DIR` environment variable.
2. **1 Cold Run + 10 Warm Runs**:
* **Cold Run (Iteration 0)**: Incurs initial disk I/O, dynamic linking, and runtime startup/interpreter overhead. Timed, but excluded from summary statistics.
* **Warm Runs (Iterations 1-10)**: Measured sequentially. Timed and included in the final mean and standard deviation calculations.


3. **Programmatic Cache Eviction**: To prevent memory page caching from skewing results, runners invalidate the file system page cache for the target file before every iteration using the POSIX system call `posix_fadvise(..., POSIX_FADV_DONTNEED)`.
4. **Programmatic Heap Cleaning**: Memory is explicitly freed and heap spaces are trimmed (e.g., via `malloc_trim` or garbage collection calls) between files and iterations to prevent memory accumulation and thrashing from affecting consecutive runs.
5. **Integrity Parity Checks**: Every single file loader validates that the streamline count (expected **5,979,093**) and total point count (expected **201,521,017**) match the exact baseline specifications. Any mismatch invalidates the timing and records an error.

---

## 📂 Repository Structure

```
trx-nature-2026-benchmark/
├── README.md                 # Scientific context, setup, and language guide
├── orchestrate.py            # Master Python controller for building, running, and reporting
├── run_benchmarks.sh         # Bash entry point setting the environment and invoking python
├── results/                  # Consolidated benchmark results
│   ├── python_results.json
│   ├── rust_results.json
│   ├── cpp_results.json
│   ├── js_results.json
│   └── summary.md            # Consolidated Markdown comparison table
├── python/
│   ├── requirements.txt      # Python library dependencies
│   ├── utils.py              # Cache eviction, memory release, and format load routing
│   └── benchmark.py          # Python load/save benchmark suite
├── rust/
│   ├── Cargo.toml            # Rust cargo manifest referencing local trx-rs
│   └── src/
│       ├── main.rs           # Rust load/save benchmark suite
│       └── utils.rs          # Rust posix_fadvise cache eviction wrapper
├── cpp/
│   ├── CMakeLists.txt        # CMake configuration linking Eigen, libzip, and trx-cpp
│   ├── utils.hpp             # C++ utility declarations
│   ├── utils.cpp             # Fast in-memory VTK, TCK, and TRK loaders
│   └── benchmark.cpp         # C++ load/save benchmark suite
└── js/
    ├── package.json          # Node dependencies (fflate, fzstd, gl-matrix)
    ├── utils.js              # Chunked file loader (>2GB bypass) and eviction wrappers
    └── benchmark.mjs         # JavaScript ES module load benchmark suite

```

---

## 💻 Language-Specific Implementations

Each language track has been engineered to optimize performance while adhering to the uniform benchmark protocol.

### 🐍 Python

The Python track utilizes the official scientific libraries in the neuroimaging ecosystem.

* **Libraries & Dependencies**:
* `numpy`: Array manipulation.
* `trx-python`: Core library for TRX memory-mapping and I/O.
* `nibabel`: Standard library for reading TRK and TCK files.
* `dipy`: Used for streamline processing utilities.
* `fury`: Used for loading and saving VTK polydata formats.


* **Memory Management**:
Triggers explicit Python garbage collection (`gc.collect()`) followed by a ctypes call to `libc.so.6`'s `malloc_trim(0)`. This forces the glibc memory allocator to release freed heap memory back to the operating system, preventing CPython memory fragmentation.
* **Cache Eviction**:
Uses Python's native `os.posix_fadvise(fd, 0, size, os.POSIX_FADV_DONTNEED)` after opening file descriptors to flush OS read caches.
* **Write Operations**:
Measures save operations for all formats (TRX, TRK, TCK, VTK).

### 🦀 Rust

The Rust track leverages the safety and raw performance of native compiled binaries.

* **Libraries & Dependencies**:
* `trx-rs` (linked via local workspace path `../../trx-rs`): High-performance Rust parser for TRX.
* `libc`: Binds POSIX functions for disk cache flushing.
* `serde` & `serde_json`: High-speed JSON serialization.


* **Optimization**:
Built using Cargo release optimization flags (`cargo build --release`).
* **Memory Management**:
Relies on Rust's compile-time RAII (Resource Acquisition Is Initialization). Objects are dropped immediately when they go out of scope. We enforce thread sleeps (`std::thread::sleep`) between iterations to allow the kernel allocator to settle.
* **Cache Eviction**:
Uses native C bindings via the `libc` crate: `libc::posix_fadvise(fd, 0, 0, libc::POSIX_FADV_DONTNEED)`.
* **Write Capability**:
Supports writing all formats (TRX, TRK, TCK, VTK). A custom, highly optimized TrackVis (.trk) writer was implemented in `rust/src/main.rs` to bypass the `trx-rs` library's intentional omission of the TRK writer.

### ⚡ C++

The C++ track represents the high-performance compiled baseline, built under strict compiler optimization.

* **Libraries & Dependencies**:
* `trx-cpp` (linked via CMake path `../../trx-cpp`): Static C++ TRX library.
* `Eigen`: Header-only linear algebra library.
* `libzip`: Used internally for reading/writing ZIP compressed TRX archives.


* **Optimization**:
Compiled using CMake in `Release` mode with maximum optimizations (`-O3`).
* **Custom Legacy Format Parsers**:
To avoid the enormous overhead of standard mesh structures, a lightweight, highly optimized binary parser was implemented in `cpp/utils.cpp`.
* *TCK/TRK/VTK*: Coordinates are counted by scanning binary data chunks directly from a file buffer rather than copying them into Eigen dynamic matrices, allowing high-performance parsing that serves as a baseline for the physics/geometry level.


* **Memory Management**:
Utilizes smart pointers and custom scopes for RAII. Calls `malloc_trim(0)` between runs to release memory pages.
* **Cache Eviction**:
Uses standard `<fcntl.h>` system calls to get a raw file descriptor and call `posix_fadvise(fd, 0, 0, POSIX_FADV_DONTNEED)`.
* **Write Capability**:
Supports writing all formats (TRX, TRK, TCK, VTK). Highly optimized C++ encoders for TCK, TRK, and VTK are implemented in `cpp/utils.cpp` utilizing low-overhead binary chunk buffering.

### 🌐 JavaScript (Node.js)

The JavaScript track evaluates the performance of the V8 JavaScript engine running under Node.js. Processing multi-gigabyte files in JS presents several engine-level challenges, which were solved using custom workarounds.

* **Libraries & Dependencies**:
* `trx-javascript` (linked locally): Core JS TRX reader.
* `fflate`: Extremely fast, pure JS zipping library.
* `fzstd`: Zstd decompression.
* `gl-matrix`: High-speed vector operations.


* **Technical Workarounds & Engine Bypasses**:
1. **Node.js 2 GiB File Limit**: Node's default `fs.readFileSync` throws a `RangeError [ERR_FS_FILE_TOO_LARGE]` when attempting to load files exceeding 2 GiB. We implemented a custom chunked binary reader in `js/utils.js` using `fs.openSync` and `fs.readSync` in a loop, pre-allocating a single large `ArrayBuffer` to bypass this V8 boundary.
2. **Shared ArrayBuffer Corruption**: Libraries like `fflate.unzipSync` decompress files into a shared backing `ArrayBuffer` to avoid memory copies. Instantiating typed arrays using `new Float32Array(data.buffer)` reads from the start of the shared buffer instead of the decompression slice, causing coordinate/offset corruption. We resolved this by explicitly passing `data.byteOffset` and `data.byteLength` parameters:
```javascript
new Float32Array(data.buffer, data.byteOffset, data.byteLength / 4)

```





```
    3.  **V8 Heap Memory Configuration**: Large datasets (up to 8.1 GB zip archives containing 6 GB geometry) cause Node.js processes to exceed the default heap limit (1.4 GB) and crash with out-of-memory (OOM) errors. The benchmark runner must be invoked with `--max-old-space-size=16384` to expand the heap limit to 16 GB.
    4.  **Garbage Collection**: Node is run with the `--expose-gc` flag. Programmatic memory reclamation is triggered before each run using `global.gc()`.
*   **Write Capability**:
    Supports writing all formats (TRX, TRK, TCK, VTK) using high-performance chunked encoders in `js/utils.js`. The TRX format is serialized directly to a zip-based archive using `fflate.zipSync`.

---

## 📊 Uniform JSON Schema

To ensure identical parsing structures, every runner output writes to `results/<language>_results.json` conforming to this exact layout:

```json
{
  "language": "python",
  "data_directory": "/home/local/USHERBROOKE/rhef1902/Libraries/trx/trx_benchmark_04_2026",
  "results": {
    "loading": {
      "f16_ui32_w_metadata.trx": [0.3842, 0.3541, 0.3129, 0.3012, 0.3204, 0.3341, 0.2981, 0.3120, 0.3042, 0.3114],
      "f32_w_metadata.trk": [3.4921, 3.2014, 3.1142, 3.0921, 3.0114, 3.1204, 2.9921, 3.0421, 3.0019, 3.1092]
    },
    "saving": {
      "f16_ui32_w_metadata.trx": [0.6841, 0.6542, 0.6014, 0.6120, 0.5982, 0.6042, 0.5891, 0.6112, 0.6021, 0.5998]
    }
  }
}

```

## 🔧 Setup & Installation (Language-by-Language)

This section provides step-by-step instructions to compile and prepare each benchmark module individually.

### 🐍 Python Setup

The Python module requires Python 3.8+ along with several scientific neuroimaging libraries.

1. **Create a Virtual Environment** (recommended to avoid package conflicts):
```bash

```



python3 -m venv venv
source venv/bin/activate

```
2.  **Install PIP Dependencies**:
    First install standard pre-requisite libraries:
    ```bash
pip install numpy nibabel dipy fury

```

3. **Install the Local `trx-python` Library**:
Since we are benchmarking the local implementation, install it in editable mode:
```bash
pip install -e ../trx-python

```



```
    *Alternatively, install all from the requirements file:*
    ```bash
    pip install -r python/requirements.txt

```

### 🦀 Rust Setup

The Rust module relies on the Cargo build system and the Rust compiler (`rustc`).

1. **Ensure Rust is installed** (via [rustup](https://rustup.rs/)):
```bash

```



rustc --version
cargo --version

```
2.  **Compilation**:
    The Rust track links dynamically to `trx-rs` at the relative sibling path `../../trx-rs`. Compiling with release flags is critical to enable compiler optimizations:
    ```bash
cd rust
cargo build --release

```

```
The compiled binary will be placed relative to the workspace at `target/release/trx-nature-2026-benchmark-rust`.

```

### ⚡ C++ Setup

The C++ benchmark runner compiles using CMake and links to the local `trx-cpp` sibling library.

1. **System Requirements**:
Ensure you have `cmake` (version 3.16+), a C++17 compatible compiler (e.g., `g++` 9+), and `libzip-dev` installed (for ZIP file parsing support).
On Debian/Ubuntu-based systems:
```bash

```



sudo apt-get install build-essential cmake libzip-dev

```
2.  **Configuration & Build**:
    Create a build directory, run CMake in Release mode, and build in parallel:
    ```bash
    cd cpp
    mkdir -p build && cd build
    cmake -DCMAKE_BUILD_TYPE=Release ..
    make -j$(nproc)

```

```
The compiled binary will be created at `cpp/build/trx_benchmark`.

```

### 🌐 JavaScript (Node.js) Setup

The JavaScript track requires Node.js (version 16 or newer) and the Node Package Manager (`npm`).

1. **Ensure Node.js and NPM are installed**:
```bash

```



node --version
npm --version

```
2.  **Install Dependencies**:
    Initialize dependencies (`fflate`, `fzstd`, and `gl-matrix`) in the `js` sub-folder:
    ```bash
cd js
npm install

```

---

## 🏃 How to Run the Benchmarks

You can run the benchmarks either using the **Master Orchestration Pipeline** (automatic building, running, and reporting) or **Individually** per language.

### Environment Variable Setup

Before running any benchmark, you **MUST** export the environment variable `TRX_BENCHMARK_DATA_DIR` pointing to the folder containing the target tractography datasets:

```bash
export TRX_BENCHMARK_DATA_DIR="/path/to/trx_benchmark_04_2026"

```

### Option A: Master Orchestrator Pipeline (Recommended)

The orchestration scripts compile all targets, run the benchmark cycles, and generate the final results table.

1. **Run Everything (Build, Run, & Report)**:
```bash

```



./run_benchmarks.sh

```
    This triggers:
    - Compilation of C++ in Release mode.
    - Compilation of Rust in Release mode.
    - JS dependency installation.
    - Full sequential benchmark execution of Python, Rust, JavaScript, and C++.
    - Aggregation of results into `results/summary.md`.

2.  **Targeted Pipeline Commands**:
    *   **Build Only**: Compile Rust and C++ runners and set up Node packages.
        ```bash
./run_benchmarks.sh build

```

```
*   **Run Only**: Execute the benchmark runs (assuming they are already compiled).
    ```bash

```

./run_benchmarks.sh run

```
    *   **Report Only**: Regenerate the Markdown comparison summary table from existing `results/*.json` files.
        ```bash
./run_benchmarks.sh report

```

### Option B: Running Languages Individually

If you want to debug or isolate execution to a single language track, run the scripts directly from the repository root:

* **Python**:
```bash
python3 python/benchmark.py

```



```
*   **Rust**:
    ```bash
    ./rust/target/release/trx-nature-2026-benchmark-rust

```

* **C++**:
```bash
./cpp/build/trx_benchmark

```



```
*   **JavaScript**:
    *CRITICAL: You must pass the `--expose-gc` flag (to allow programmatic garbage collection) and expand heap space using `--max-old-space-size=16384` to prevent Out Of Memory (OOM) crashes on large files.*
    ```bash
    node --expose-gc --max-old-space-size=16384 js/benchmark.mjs

```

After running individual modules, their outputs will be saved to `results/<language>_results.json`. You can then consolidate them into the final report by running:

```bash
python3 orchestrate.py report

```