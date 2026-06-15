import os
import sys
import json
import time
import shutil
import numpy as np
import nibabel as nib
from fury import io

# Ensure local python directory is in import path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import (release_memory, evict_from_cache, load_data)

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

EXPECTED_STREAMLINES = None
EXPECTED_POINTS = None

def get_counts(obj):
    if hasattr(obj, 'streamlines'):
        streamlines = obj.streamlines
        return len(streamlines), len(streamlines._data)
    elif hasattr(obj, 'GetNumberOfLines'):
        return obj.GetNumberOfLines(), obj.GetNumberOfPoints()
    else:
        raise ValueError(f"Unknown object type: {type(obj)}")

def main():
    data_dir = os.environ.get("TRX_BENCHMARK_DATA_DIR")
    if not data_dir:
        sys.stderr.write("[ERROR] Environment variable TRX_BENCHMARK_DATA_DIR is not set.\n")
        sys.exit(1)
    
    if not os.path.isdir(data_dir):
        sys.stderr.write(f"[ERROR] TRX_BENCHMARK_DATA_DIR directory '{data_dir}' does not exist.\n")
        sys.exit(1)

    results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
    os.makedirs(results_dir, exist_ok=True)

    tmp_save_dir = os.path.join(results_dir, "tmp_benchmark_saving")
    os.makedirs(tmp_save_dir, exist_ok=True)

    results = {
        "language": "python",
        "data_directory": data_dir,
        "results": {
            "loading": {},
            "saving": {}
        }
    }

    for filename in FILENAMES:
        filepath = os.path.join(data_dir, filename)
        _, ext = os.path.splitext(filename)

        if not os.path.exists(filepath):
            sys.stderr.write(f"[ERROR] File not found: {filepath}\n")
            results["results"]["loading"][filename] = None
            results["results"]["saving"][filename] = None
            continue

        print(f"Benchmarking {filename}...")
        
        # 1. Benchmark Loading
        load_times = []
        obj = None
        loading_failed = False

        for i in range(11):
            evict_from_cache(filepath)
            release_memory()

            t0 = time.time()
            try:
                obj = load_data(filepath)
                
                if hasattr(obj, 'streamlines'):
                    obj.streamlines._data = obj.streamlines._data.astype(np.float32)
                duration = time.time() - t0
                
                # Verify integrity
                streamline_count, point_count = get_counts(obj)
                global EXPECTED_STREAMLINES, EXPECTED_POINTS
                if EXPECTED_STREAMLINES is None:
                    EXPECTED_STREAMLINES = streamline_count
                    EXPECTED_POINTS = point_count
                
                if streamline_count != EXPECTED_STREAMLINES or point_count != EXPECTED_POINTS:
                    raise ValueError(
                        f"Integrity check failed: expected {EXPECTED_STREAMLINES} streamlines "
                        f"and {EXPECTED_POINTS} points, got {streamline_count} and {point_count}"
                    )
            except Exception as e:
                sys.stderr.write(f"[ERROR] Loading failed for {filename} at iteration {i}: {e}\n")
                loading_failed = True
                break

            if i == 0:
                print(f"  Load Cold Run: {duration:.4f}s")
            else:
                load_times.append(duration)
                print(f"  Load Warm Run {i}: {duration:.4f}s")

        if loading_failed:
            results["results"]["loading"][filename] = None
            results["results"]["saving"][filename] = None
            if obj is not None:
                del obj
            release_memory()
            continue

        # Save load results
        results["results"]["loading"][filename] = load_times
        avg_load = np.mean(load_times)
        std_load = np.std(load_times)
        print(f"  Summary Load: {avg_load:.4f} +/- {std_load:.4f} seconds")

        # 2. Benchmark Saving
        save_times = []
        saving_failed = False

        for i in range(11):
            release_memory()
            save_path = os.path.join(tmp_save_dir, f"tmp_save_{i}{ext}")

            t0 = time.time()
            try:
                if ext in [".trk", ".tck"]:
                    nib.streamlines.save(obj, save_path)
                elif ext in [".vtk", ".vtp", ".fib"]:
                    io.save_polydata(obj, save_path, binary=True)
                elif ext == ".trx":
                    from trx.trx_file_memmap import save as save_trx
                    save_trx(obj, save_path)
                duration = time.time() - t0
            except Exception as e:
                sys.stderr.write(f"[ERROR] Saving failed for {filename} at iteration {i}: {e}\n")
                saving_failed = True
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                    except Exception:
                        pass
                break

            if i == 0:
                print(f"  Save Cold Run: {duration:.4f}s")
            else:
                save_times.append(duration)
                print(f"  Save Warm Run {i}: {duration:.4f}s")

            # Clean up temp file immediately
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except Exception as e:
                    sys.stderr.write(f"[WARN] Failed to delete temp file {save_path}: {e}\n")

        # Cleanup loaded object
        del obj
        release_memory()

        if saving_failed:
            results["results"]["saving"][filename] = None
        else:
            results["results"]["saving"][filename] = save_times
            avg_save = np.mean(save_times)
            std_save = np.std(save_times)
            print(f"  Summary Save: {avg_save:.4f} +/- {std_save:.4f} seconds")
        
        print()

    # Final cleanup of temp directory
    try:
        shutil.rmtree(tmp_save_dir)
    except Exception:
        pass

    # Save results
    output_json = os.path.join(results_dir, "python_results.json")
    with open(output_json, "w") as f:
        json.dump(results, f, indent=4)
    print(f"Results saved to {output_json}")

if __name__ == "__main__":
    main()
