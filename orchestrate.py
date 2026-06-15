#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import numpy as np

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

def print_banner(msg):
    print("=" * 60)
    print(f" {msg}")
    print("=" * 60)

def check_env():
    data_dir = os.environ.get("TRX_BENCHMARK_DATA_DIR")
    if not data_dir:
        print("[ERROR] Environment variable TRX_BENCHMARK_DATA_DIR is not set.", file=sys.stderr)
        print("Please set it pointing to the folder containing tractography benchmark files.", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(data_dir):
        print(f"[ERROR] TRX_BENCHMARK_DATA_DIR directory '{data_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)
    
    # Check for reference volume
    ref_vol = os.path.join(data_dir, "fa.nii.gz")
    if not os.path.isfile(ref_vol):
        print(f"[WARNING] Reference volume 'fa.nii.gz' not found in '{data_dir}'.", file=sys.stderr)
        print("Some formats/loaders (like dipy/nibabel for TCK/VTK) might fail.", file=sys.stderr)
    return data_dir

def build_rust():
    print_banner("Building Rust benchmark runner...")
    try:
        env = os.environ.copy()
        cargo_bin = os.path.expanduser("~/.cargo/bin")
        if cargo_bin not in env.get("PATH", ""):
            env["PATH"] = f"{cargo_bin}:{env.get('PATH', '')}"
        subprocess.run(["cargo", "build", "--release"], cwd="rust", env=env, check=True)
        print("[SUCCESS] Rust runner compiled.")
    except Exception as e:
        print(f"[ERROR] Rust runner compilation failed: {e}", file=sys.stderr)

def build_cpp():
    print_banner("Building C++ benchmark runner...")
    try:
        os.makedirs("cpp/build", exist_ok=True)
        subprocess.run(["cmake", "-DCMAKE_BUILD_TYPE=Release", ".."], cwd="cpp/build", check=True)
        subprocess.run(["make", "-j"], cwd="cpp/build", check=True)
        print("[SUCCESS] C++ runner compiled.")
    except Exception as e:
        print(f"[ERROR] C++ runner compilation failed (ensure cpp directory exists and is implemented): {e}", file=sys.stderr)

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
        binary_path = os.path.join("rust", "target", "release", "trx-nature-2026-benchmark-rust")
        if not os.path.isfile(binary_path):
            # Fallback to local execution directory or cargo run
            subprocess.run(["cargo", "run", "--release"], cwd="rust", check=True)
        else:
            subprocess.run([f"./{binary_path}"], check=True)
        print("[SUCCESS] Rust benchmarks completed.")
    except Exception as e:
        print(f"[ERROR] Rust benchmarks failed: {e}", file=sys.stderr)

def run_js():
    print_banner("Running JavaScript benchmarks...")
    try:
        # Run node with expanded heap memory to handle large files
        subprocess.run(["node", "--expose-gc", "--max-old-space-size=16384", "js/benchmark.mjs"], check=True)
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
            print("[WARNING] C++ benchmark executable not found. Skipping execution.", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] C++ benchmarks failed: {e}", file=sys.stderr)

def load_results():
    results = {}
    for lang in LANGUAGES:
        results[lang] = None
        results_file = os.path.join("results", f"{lang}_results.json")
        if os.path.isfile(results_file):
            try:
                with open(results_file, "r") as f:
                    results[lang] = json.load(f)
            except Exception as e:
                print(f"[WARNING] Failed to load results for {lang}: {e}", file=sys.stderr)
    return results

def compute_stats(runs):
    if not runs:
        return "N/A"
    # Filter out None values or invalid elements
    valid_runs = [r for r in runs if r is not None]
    if not valid_runs:
        return "N/A"
    
    mean = np.mean(valid_runs)
    std = np.std(valid_runs)
    return f"{mean:.4f} ± {std:.4f}"

def generate_report():
    print_banner("Generating consolidated benchmark report...")
    results = load_results()
    
    headers = [
        "Format / Filename",
        "Python Load (s)", "Python Save (s)",
        "Rust Load (s)", "Rust Save (s)",
        "C++ Load (s)", "C++ Save (s)",
        "JS Load (s)", "JS Save (s)"
    ]
    
    md_lines = []
    md_lines.append("# Consolidated Multi-Language Tractography Benchmark Results")
    md_lines.append(f"Data directory: `{os.environ.get('TRX_BENCHMARK_DATA_DIR')}`")
    md_lines.append("")
    md_lines.append("| " + " | ".join(headers) + " |")
    md_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    
    for filename in FILENAMES:
        row = [f"`{filename}`"]
        
        for lang in LANGUAGES:
            lang_data = results.get(lang)
            load_str = "N/A"
            save_str = "N/A"
            
            if lang_data and "results" in lang_data:
                res = lang_data["results"]
                
                # Extract loading times
                loading_runs = res.get("loading", {}).get(filename)
                load_str = compute_stats(loading_runs)
                
                # Extract saving times
                saving_runs = res.get("saving", {}).get(filename)
                save_str = compute_stats(saving_runs)
            
            row.extend([load_str, save_str])
            
        md_lines.append("| " + " | ".join(row) + " |")
        
    report = "\n".join(md_lines)
    
    # Save report
    os.makedirs("results", exist_ok=True)
    summary_file = os.path.join("results", "summary.md")
    with open(summary_file, "w") as f:
        f.write(report)
        
    print(report)
    print("\n" + "=" * 60)
    print(f"Summary saved to {summary_file}")
    print("=" * 60)

def main():
    check_env()
    
    # If run with arguments, check what was requested
    args = sys.argv[1:]
    
    if not args or "all" in args:
        # Build phase
        build_rust()
        build_cpp()
        setup_js()
        
        # Run phase
        run_python()
        run_rust()
        run_js()
        run_cpp()
        
        # Report phase
        generate_report()
    elif "report" in args:
        generate_report()
    elif "clean" in args:
        print_banner("Cleaning benchmark artifacts...")
        import shutil
        if os.path.exists("results/tmp_benchmark_saving"):
            shutil.rmtree("results/tmp_benchmark_saving", ignore_errors=True)
        for f in os.listdir("results") if os.path.exists("results") else []:
            if f.endswith(".json"):
                os.remove(os.path.join("results", f))
        print("[SUCCESS] Cleanup complete.")
    else:
        if "build" in args:
            build_rust()
            build_cpp()
            setup_js()
        if "run" in args:
            run_python()
            run_rust()
            run_js()
            run_cpp()
        if "report" in args:
            generate_report()

if __name__ == "__main__":
    main()
