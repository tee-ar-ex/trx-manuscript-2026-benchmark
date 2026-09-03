#!/usr/bin/env python
import os
import sys
import time
import subprocess
import shutil
import numpy as np
import trx.trx_file_memmap as trx_mmap
from nibabel.streamlines.tractogram import Tractogram
from nibabel.streamlines.array_sequence import ArraySequence

TEST_DIR = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "test_data")
TMP_DIR = os.path.join(TEST_DIR, "tmp_extreme")
REF_PATH = os.path.join(TEST_DIR, "fa.nii")


def run_language(lang, input_path, output_path, expect_fail=False):
    runners = {
        "python": [
            "python3", os.path.join(TEST_DIR, "run_py.py"),
            input_path, output_path
        ],
        "js": [
            "node", "--expose-gc", "--max-old-space-size=16384",
            os.path.join(TEST_DIR, "run_js.mjs"),
            input_path, output_path
        ],
        "cpp": [
            "./test_cpp", input_path, output_path
        ],
        "rust": [
            "cargo", "run", "--release", "--",
            input_path, output_path
        ]
    }

    cwd_map = {
        "cpp": os.path.join(TEST_DIR, "cpp"),
        "rust": os.path.join(TEST_DIR, "rust"),
    }

    cmd = runners[lang]
    kwargs = {"check": True, "stdout": subprocess.PIPE,
              "stderr": subprocess.PIPE}
    if lang in cwd_map:
        kwargs["cwd"] = cwd_map[lang]

    try:
        t0 = time.time()
        subprocess.run(cmd, **kwargs)
        dur = time.time() - t0
        if expect_fail:
            return False, dur
        return True, dur
    except subprocess.CalledProcessError as e:
        if expect_fail:
            return True, 0
        print(f"[{lang}] Error: {e.stderr.decode('utf-8', errors='ignore')}")
        return False, 0


def test_empty():
    print("\n=== 1. Empty/Minimal TRX Test ===")
    os.makedirs(TMP_DIR, exist_ok=True)
    filepath = os.path.join(TMP_DIR, "empty.trx")

    tractogram = Tractogram(streamlines=[])
    trx = trx_mmap.TrxFile.from_tractogram(tractogram, reference=REF_PATH)
    trx_mmap.save(trx, filepath)

    failed_langs = []
    for lang in ["python", "js", "cpp", "rust"]:
        out_path = os.path.join(TMP_DIR, f"empty_{lang}.trx")
        success, _ = run_language(lang, filepath, out_path)
        if success:
            print(f"[{lang}] PASSED")
        else:
            print(f"[{lang}] FAILED")
            failed_langs.append(lang)

    return not failed_langs


def test_extreme_values():
    print("\n=== 2. Extreme Values Relay Test ===")
    filepath = os.path.join(TMP_DIR, "extreme.trx")

    pos = np.array([[np.nan, np.inf, -np.inf],
                   [0.0, 1.0, -1.0]], dtype=np.float32)
    streamlines = ArraySequence([pos])

    dpv = {
        "max_uint64": ArraySequence([np.array([[np.iinfo(np.uint64).max], [0]], dtype=np.uint64)]),
        "min_int16": ArraySequence([np.array([[np.iinfo(np.int16).min], [0]], dtype=np.int16)])
    }

    tractogram = Tractogram(streamlines=streamlines, data_per_point=dpv)
    trx = trx_mmap.TrxFile.from_tractogram(tractogram, reference=REF_PATH)
    trx_mmap.save(trx, filepath)

    current_file = filepath
    failed_langs = []
    for lang in ["python", "js", "cpp", "rust"]:
        next_file = os.path.join(TMP_DIR, f"extreme_out_{lang}.trx")
        success, _ = run_language(lang, current_file, next_file)
        if success:
            print(f"[{lang}] PASSED generation")
            current_file = next_file
        else:
            print(f"[{lang}] FAILED generation")
            failed_langs.append(lang)

    return not failed_langs


def test_corrupted():
    print("\n=== 3. Corrupted / Truncated File Test ===")
    filepath = os.path.join(TMP_DIR, "valid.trx")
    tractogram = Tractogram(streamlines=[np.zeros((1, 3), dtype=np.float32)])
    trx = trx_mmap.TrxFile.from_tractogram(tractogram, reference=REF_PATH)
    trx_mmap.save(trx, filepath)

    corrupted_path = os.path.join(TMP_DIR, "corrupted.trx")
    with open(filepath, "rb") as f:
        data = f.read()
    with open(corrupted_path, "wb") as f:
        f.write(data[:-100])  # Truncate 100 bytes

    failed_langs = []
    for lang in ["python", "js", "cpp", "rust"]:
        out_path = os.path.join(TMP_DIR, f"corrupted_{lang}.trx")
        success, _ = run_language(
            lang, corrupted_path, out_path, expect_fail=True)
        if success:
            print(f"[{lang}] PASSED (Graceful fail on corrupted file)")
        else:
            print(f"[{lang}] FAILED (Did not error gracefully)")
            failed_langs.append(lang)

    return not failed_langs


def test_dict_stress():
    print("\n=== 4. Dictionary Stress Test ===")
    filepath = os.path.join(TMP_DIR, "stress.trx")

    tractogram = Tractogram(streamlines=[np.zeros((1, 3), dtype=np.float32)])
    trx = trx_mmap.TrxFile.from_tractogram(tractogram, reference=REF_PATH)
    trx.groups = {f"group_{i}": np.array(
        [], dtype=np.uint32) for i in range(10000)}
    trx_mmap.save(trx, filepath)

    failed_langs = []
    for lang in ["python", "js", "cpp", "rust"]:
        out_path = os.path.join(TMP_DIR, f"stress_{lang}.trx")
        success, dur = run_language(lang, filepath, out_path)
        if success:
            print(f"[{lang}] PASSED in {dur:.2f}s")
        else:
            print(f"[{lang}] FAILED")
            failed_langs.append(lang)

    return not failed_langs


def test_scalability():
    print("\n=== 5. 1GB Scalability & Throughput Equivalence Test ===")
    filepath = os.path.join(TMP_DIR, "scale.trx")
    if not os.path.exists(filepath):
        print("Generating ~1GB test file (160M vertices)...")
        n_vertices = 160_000_000

        tmp_manual = os.path.join(TMP_DIR, "scale_manual")
        os.makedirs(tmp_manual, exist_ok=True)

        import json
        header = {
            "NB_VERTICES": n_vertices,
            "NB_STREAMLINES": n_vertices // 160,
            "VOXEL_TO_RASMM": np.eye(4).tolist(),
            "DIMENSIONS": [1, 1, 1]
        }
        with open(os.path.join(tmp_manual, "header.json"), "w") as f:
            json.dump(header, f)

        pos = np.zeros((n_vertices, 3), dtype=np.float16)
        offsets = np.arange(0, n_vertices, 160, dtype=np.uint64)
        # Ensure last offset points to end
        offsets = np.append(offsets, np.uint64(n_vertices))

        pos.tofile(os.path.join(tmp_manual, "positions.3.float16"))
        offsets.tofile(os.path.join(tmp_manual, "offsets.uint64"))

        import zipfile
        with zipfile.ZipFile(filepath, "w", zipfile.ZIP_STORED) as zf:
            zf.write(os.path.join(tmp_manual, "header.json"), "header.json")
            zf.write(os.path.join(tmp_manual, "positions.3.float16"),
                     "positions.3.float16")
            zf.write(os.path.join(tmp_manual, "offsets.uint64"),
                     "offsets.uint64")

        shutil.rmtree(tmp_manual)
    else:
        print("Using existing 1GB test file.")

    file_size_mb = os.path.getsize(filepath) / 1000000.0
    times = {}
    failed_langs = []

    for lang in ["python", "js", "cpp", "rust"]:
        out_path = os.path.join(TMP_DIR, f"scale_{lang}.trx")
        print(f"Running {lang}...")
        success, dur = run_language(lang, filepath, out_path)
        if success:
            tp = file_size_mb / dur if dur > 0 else 0
            print(f"  [{lang}] Duration: {dur:.2f}s | Throughput: {tp:.0f} MB/s")
            times[lang] = dur
        else:
            print(f"  [{lang}] FAILED")
            failed_langs.append(lang)

    langs = ["python", "js", "cpp", "rust"]
    ratios = {}
    violations = []
    from itertools import combinations
    if not times:
        print("No timing data collected.")
        return False
    else:
        for a, b in combinations(langs, 2):
            if a not in times or b not in times:
                print(
                    f"Skipping pair {a}/{b}: missing timing for one of the languages.")
                continue
            ta = times[a]
            tb = times[b]
            if tb == 0:
                ratio = float("inf")
            else:
                ratio = ta / tb
            ratios[f"{a}/{b}"] = ratio

            # Python's memory-mapped writes are natively much faster due to OS page cache.
            # Relax the bound if Python is involved.
            min_ratio = 0.25
            max_ratio = 4.0

            if not (min_ratio <= ratio <= max_ratio):
                violations.append((a, b, ratio))

        print("Pairwise duration ratios:")
        for k, v in sorted(ratios.items()):
            print(f"  {k}: {v:.3f}")

        if violations:
            print("\nViolations (ratio outside [0.25, 4.0]):")
            for a, b, r in violations:
                print(f"  {a}/{b} = {r:.3f}")
        else:
            print("\nAll pairwise ratios within [0.25, 4.0].")

    return not failed_langs and not violations


if __name__ == "__main__":
    results = {}
    try:
        results["empty"] = test_empty()
        results["extreme_values"] = test_extreme_values()
        results["corrupted"] = test_corrupted()
        results["dict_stress"] = test_dict_stress()
        results["scalability"] = test_scalability()
    finally:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    failed = [name for name, passed in results.items() if not passed]
    if failed:
        raise RuntimeError(f"extreme_tests failed: {', '.join(failed)}")
