#!/usr/bin/env python
import os
import sys
import subprocess
import zipfile
import shutil
import numpy as np
import trx.trx_file_memmap as trx_mmap

TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")
TMP_DIR = os.path.join(TEST_DIR, "tmp_compression")
GS_FILE = os.path.join(TEST_DIR, "gs_from_py.trx")
REF_PATH = os.path.join(TEST_DIR, "fa.nii")

def run_language(lang, input_path, output_path):
    runners = {
        "python": ["python3", os.path.join(TEST_DIR, "run_py.py"), input_path, output_path],
        "js": ["node", "--expose-gc", "--max-old-space-size=16384", os.path.join(TEST_DIR, "run_js.mjs"), input_path, output_path],
        "cpp": ["./test_cpp", input_path, output_path],
        "rust": ["cargo", "run", "--release", "--", input_path, output_path]
    }
    cwd_map = {"cpp": os.path.join(TEST_DIR, "cpp"), "rust": os.path.join(TEST_DIR, "rust")}
    
    cmd = runners[lang]
    kwargs = {"check": True, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
    if lang in cwd_map:
        kwargs["cwd"] = cwd_map[lang]
        
    try:
        subprocess.run(cmd, **kwargs)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[{lang}] Error: {e.stderr.decode('utf-8', errors='ignore')}")
        return False

def test_compression():
    os.makedirs(TMP_DIR, exist_ok=True)
    compressed_initial = os.path.join(TMP_DIR, "compressed_initial.trx")
    
    print("1. Loading gold standard and saving compressed (Python)...")
    trx = trx_mmap.load(GS_FILE)
    trx = trx.to_memory()
    # Save with ZIP_DEFLATED (highest standard compression in python zipfile without lzma/bzip2)
    trx_mmap.save(trx, compressed_initial, compression_standard=zipfile.ZIP_DEFLATED)
    
    orig_size = os.path.getsize(GS_FILE)
    comp_size = os.path.getsize(compressed_initial)
    print(f"   Original size: {orig_size} bytes")
    print(f"   Compressed size: {comp_size} bytes")
    
    print("2. Relay loading and saving across languages...")
    current_file = compressed_initial
    
    langs = ["python", "js", "cpp", "rust"]
    for lang in langs:
        next_file = os.path.join(TMP_DIR, f"relay_{lang}.trx")
        success = run_language(lang, current_file, next_file)
        if success:
            print(f"   [{lang}] PASSED loading compressed file and saving")
            current_file = next_file
        else:
            print(f"   [{lang}] FAILED")
            sys.exit(1)
            
    print("3. Validating data integrity after relay...")
    final_trx = trx_mmap.load(current_file)
    
    # Check against original
    if not np.allclose(trx.streamlines._data, final_trx.streamlines._data, atol=1e-4):
        print("   FAILED: Coordinates mismatch after relay.")
        sys.exit(1)
    else:
        print("   PASSED: Coordinates match original.")
        
    print("\nCompression tests passed successfully!")

if __name__ == "__main__":
    try:
        test_compression()
    finally:
        shutil.rmtree(TMP_DIR, ignore_errors=True)
