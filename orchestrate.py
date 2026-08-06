#!/usr/bin/env python
import os
import sys
import json
import subprocess
import numpy as np
import argparse
import shutil
import glob

FILENAMES = [
    "f16_ui32_w_metadata.trx", "f16_ui32_wo_metadata.trx",
    "f16_ui64_w_metadata.trx", "f16_ui64_wo_metadata.trx",
    "f32_ui64_w_metadata.trx", "f32_ui64_wo_metadata.trx",
    "f64_ui32_w_metadata.trx", "f64_ui32_wo_metadata.trx",
    "f32_ui32_w_metadata.trx", "f32_ui32_wo_metadata.trx",
    "f64_ui64_w_metadata.trx", "f64_ui64_wo_metadata.trx",
    "f32_w_metadata.trk", "f32_wo_metadata.trk", "f32.tck",
    "f32_ui32_wo_metadata.vtk", "f32_ui64_wo_metadata.vtk",
    "f64_ui32_wo_metadata.vtk", "f64_ui64_wo_metadata.vtk",
    "f32_ui64_w_metadata.vtk", "f64_ui64_w_metadata.vtk"
]

LANGUAGES = ["python", "rust", "cpp", "javascript"]

# Control the number of iterations for all benchmarks
# (e.g., set to 1 for quick testing, 10 for thorough benchmarking)
NUM_ITERATIONS = 10
os.environ["TRX_BENCHMARK_ITERATIONS"] = str(NUM_ITERATIONS)



def print_banner(msg):
    print("=" * 60)
    print(f" {msg}")
    print("=" * 60)


def check_env():
    data_dir = os.environ.get("TRX_BENCHMARK_DATA_DIR")
    if not data_dir:
        default_dir = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "trx_benchmark_04_2026"))
        if os.path.isdir(default_dir):
            print(f"[INFO] Found default benchmark dataset at {default_dir}")
            os.environ["TRX_BENCHMARK_DATA_DIR"] = default_dir
            data_dir = default_dir
        else:
            print(
                "[ERROR] Environment variable TRX_BENCHMARK_DATA_DIR is not set.",
                file=sys.stderr)
            print(
                "Please set it pointing to the folder containing tractography benchmark files.",
                file=sys.stderr)
            sys.exit(1)
    if not os.path.isdir(data_dir):
        print(
            f"[ERROR] TRX_BENCHMARK_DATA_DIR directory '{data_dir}' does not exist.",
            file=sys.stderr)
        sys.exit(1)

    # Check for reference volume
    ref_vol = os.path.join(data_dir, "fa.nii.gz")
    if not os.path.isfile(ref_vol):
        print(
            f"[WARNING] Reference volume 'fa.nii.gz' not found in '{data_dir}'.",
            file=sys.stderr)
        print(
            "Some formats/loaders (like dipy/nibabel for TCK/VTK) might fail.",
            file=sys.stderr)
    return data_dir


def build_rust():
    print_banner("Building Rust benchmark runner...")
    try:
        env = os.environ.copy()
        cargo_bin = os.path.expanduser("~/.cargo/bin")
        if cargo_bin not in env.get("PATH", ""):
            env["PATH"] = f"{cargo_bin}:{env.get('PATH', '')}"
        subprocess.run(["cargo", "build", "--release"],
                       cwd="rust", env=env, check=True)
        subprocess.run(["cargo", "build", "--release"],
                       cwd="test_data/rust", env=env, check=True)
        print("[SUCCESS] Rust runners compiled.")
    except Exception as e:
        print(f"[ERROR] Rust runner compilation failed: {e}", file=sys.stderr)


def build_cpp():
    print_banner("Building C++ benchmark runner...")
    try:
        os.makedirs("cpp/build", exist_ok=True)
        subprocess.run(["cmake", "-DCMAKE_BUILD_TYPE=Release",
                       ".."], cwd="cpp/build", check=True)
        subprocess.run(["make", "-j"], cwd="cpp/build", check=True)

        os.makedirs("test_data/cpp/build", exist_ok=True)
        subprocess.run(["cmake", "-DCMAKE_BUILD_TYPE=Release",
                       ".."], cwd="test_data/cpp/build", check=True)
        subprocess.run(["make", "-j"], cwd="test_data/cpp/build", check=True)
        import shutil
        if os.path.exists("test_data/cpp/build/test_cpp"):
            shutil.copy2("test_data/cpp/build/test_cpp",
                         "test_data/cpp/test_cpp")

        print("[SUCCESS] C++ runners compiled.")
    except Exception as e:
        print(
            f"[ERROR] C++ runner compilation failed (ensure cpp directory exists and is implemented): {e}",
            file=sys.stderr)


def setup_js():
    print_banner("Setting up JavaScript dependencies...")
    try:
        subprocess.run(["npm", "install"], cwd="js", check=True)
        print("[SUCCESS] JS dependencies installed.")
    except Exception as e:
        print(f"[ERROR] JS setup failed: {e}", file=sys.stderr)


def run_python():
    print_banner("Running Python benchmarks...")
    try:
        subprocess.run(["python3", "python/benchmark.py"], check=True)
        print("[SUCCESS] Python benchmarks completed.")
    except Exception as e:
        print(f"[ERROR] Python benchmarks failed: {e}", file=sys.stderr)


def run_rust():
    print_banner("Running Rust benchmarks...")
    try:
        binary_path = os.path.join(
            "rust",
            "target",
            "release",
            "trx-nature-2026-benchmark-rust")
        if not os.path.isfile(binary_path):
            subprocess.run(["cargo", "run", "--release",
                           "--manifest-path", "rust/Cargo.toml"], check=True)
        else:
            subprocess.run([f"./{binary_path}"], check=True)
        print("[SUCCESS] Rust benchmarks completed.")
    except Exception as e:
        print(f"[ERROR] Rust benchmarks failed: {e}", file=sys.stderr)


def run_js():
    print_banner("Running JavaScript benchmarks...")
    try:
        subprocess.run(["node",
                        "--expose-gc",
                        "--max-old-space-size=16384",
                        "js/benchmark.mjs"],
                       check=True)
        print("[SUCCESS] JavaScript benchmarks completed.")
    except Exception as e:
        print(f"[ERROR] JavaScript benchmarks failed: {e}", file=sys.stderr)


def run_cpp():
    print_banner("Running C++ benchmarks...")
    try:
        binary_path = os.path.join("cpp", "build", "trx_benchmark")
        if os.path.isfile(binary_path):
            subprocess.run([f"./{binary_path}"], check=True)
            print("[SUCCESS] C++ benchmarks completed.")
        else:
            print(
                "[WARNING] C++ benchmark executable not found. Skipping execution.",
                file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] C++ benchmarks failed: {e}", file=sys.stderr)


def load_results(out_dir):
    results = {}
    for lang in LANGUAGES:
        results[lang] = None
        results_file = os.path.join(out_dir, f"{lang}_results.json")
        if os.path.isfile(results_file):
            try:
                with open(results_file, "r") as f:
                    results[lang] = json.load(f)
            except Exception as e:
                print(
                    f"[WARNING] Failed to load results for {lang}: {e}",
                    file=sys.stderr)
    return results


def compute_stats(runs, file_size_mb=None):
    if not runs:
        return "N/A"
    valid_runs = [r for r in runs if r is not None]
    if not valid_runs:
        return "N/A"

    mean = np.mean(valid_runs)
    std = np.std(valid_runs)
    res = f"{mean:.4f} ± {std:.4f}"
    if file_size_mb and mean > 0:
        throughput = file_size_mb / mean
        res += f" ({throughput:.0f} MB/s)"
    return res


def generate_report(out_dir):
    print_banner("Generating consolidated benchmark report...")
    results = load_results(out_dir)

    headers = [
        "Format / Filename",
        "Python Load (s)", "Python Save (s)",
        "Rust Load (s)", "Rust Save (s)",
        "C++ Load (s)", "C++ Save (s)",
        "JS Load (s)", "JS Save (s)"
    ]

    md_lines = []
    md_lines.append(
        "# Consolidated Multi-Language Tractography Benchmark Results")
    md_lines.append(
        f"Data directory: `{os.environ.get('TRX_BENCHMARK_DATA_DIR')}`")
    md_lines.append("")
    md_lines.append("| " + " | ".join(headers) + " |")
    md_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for filename in FILENAMES:
        row = [f"`{filename}`"]

        file_size_mb = None
        data_dir = os.environ.get('TRX_BENCHMARK_DATA_DIR')
        if data_dir:
            filepath = os.path.join(data_dir, filename)
            if os.path.exists(filepath):
                file_size_mb = os.path.getsize(filepath) / 1000000.0

        for lang in LANGUAGES:
            lang_data = results.get(lang)
            load_str = "N/A"
            save_str = "N/A"

            if lang_data and "results" in lang_data:
                res = lang_data["results"]

                loading_runs = res.get("loading", {}).get(filename)
                load_str = compute_stats(loading_runs, file_size_mb)

                saving_runs = res.get("saving", {}).get(filename)
                save_str = compute_stats(saving_runs, file_size_mb)

            row.extend([load_str, save_str])

        md_lines.append("| " + " | ".join(row) + " |")

    report = "\n".join(md_lines)

    os.makedirs(out_dir, exist_ok=True)
    summary_file = os.path.join(out_dir, "summary.md")
    with open(summary_file, "w") as f:
        f.write(report)

    print(report)
    print("\n" + "=" * 60)
    print(f"Summary saved to {summary_file}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Language Tractography Benchmark Orchestrator")
    parser.add_argument("--build", action="store_true",
                        help="Compile and set up runners")
    parser.add_argument("--run", action="store_true",
                        help="Execute the benchmark runners")
    parser.add_argument("--clean", action="store_true",
                        help="Clean build artifacts and temporary files")
    parser.add_argument("--summary", action="store_true",
                        help="Generate the markdown summary table")
    parser.add_argument("--all", action="store_true",
                        help="Execute build, run, and summary phases")
    parser.add_argument("-f", "--force_overwrite", action="store_true",
                        help="Force overwrite of existing benchmark outputs")
    parser.add_argument("--out_dir", default="results",
                        help="Directory to load/save JSON and summary output")
    parser.add_argument("--trx_benchmark_data_dir",
                        help="Override the dataset input directory path")

    args = parser.parse_args()

    # Apply environment overrides
    if args.trx_benchmark_data_dir:
        os.environ["TRX_BENCHMARK_DATA_DIR"] = os.path.abspath(
            args.trx_benchmark_data_dir)

    if args.force_overwrite:
        os.environ["TRX_BENCHMARK_FORCE_OVERWRITE"] = "1"

    os.environ["TRX_BENCHMARK_OUT_DIR"] = os.path.abspath(args.out_dir)

    check_env()

    # If no action is specified, default to all
    if not (args.build or args.clean or args.run or args.summary or args.all):
        args.all = True

    if args.clean:
        print_banner("Cleaning benchmark artifacts...")
        shutil.rmtree("cpp/build", ignore_errors=True)
        shutil.rmtree("rust/target", ignore_errors=True)
        shutil.rmtree("js/node_modules", ignore_errors=True)
        shutil.rmtree(args.out_dir, ignore_errors=True)
        shutil.rmtree("test_data/cpp/CMakeFiles", ignore_errors=True)
        shutil.rmtree("test_data/cpp/trx-cpp-build", ignore_errors=True)
        shutil.rmtree("test_data/cpp/_deps", ignore_errors=True)

        for f in glob.glob("test_data/tmp*") + glob.glob("test_data/relay*"):
            try:
                os.remove(f)
            except BaseException:
                pass
        for f in ["test_cpp", "CMakeCache.txt", "Makefile", "cmake_install.cmake"]:
            try:
                os.remove(os.path.join("test_data/cpp", f))
            except BaseException:
                pass

        print("[SUCCESS] Cleanup complete.")

        # If ONLY clean was passed, exit early
        if not (args.build or args.run or args.summary or args.all):
            return

    if args.all or args.build:
        build_rust()
        build_cpp()
        setup_js()

    if args.all or args.run:
        # Create output directory for runners to use if they respect TRX_BENCHMARK_OUT_DIR
        os.makedirs(args.out_dir, exist_ok=True)
        run_python()
        run_rust()
        run_js()
        run_cpp()

    if args.all or args.summary:
        generate_report(args.out_dir)


if __name__ == "__main__":
    main()
