import os
import sys
import subprocess
import glob
import numpy as np
from trx.trx_file_memmap import load

BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DIR = os.path.join(BENCH_DIR, "test_data")

def run_tests_for_file(input_trx):
    print(f"\n======================================")
    print(f"Testing file: {os.path.basename(input_trx)}")
    print(f"======================================")

    print("Running Python...")
    subprocess.run(["python", os.path.join(TEST_DIR, "run_py.py"), input_trx, os.path.join(TEST_DIR, "tmp_python.trx")], check=True)

    print("Running JavaScript...")
    subprocess.run(["node", os.path.join(TEST_DIR, "run_js.mjs"), input_trx, os.path.join(TEST_DIR, "tmp_js.trx")], check=True)

    print("Running C++...")
    subprocess.run(["./test_cpp", input_trx, os.path.join(TEST_DIR, "tmp_cpp.trx")], cwd=os.path.join(TEST_DIR, "cpp"), check=True)

    print("Running Rust...")
    subprocess.run(["cargo", "run", "--release", "--", input_trx, os.path.join(TEST_DIR, "tmp_rust.trx")], cwd=os.path.join(TEST_DIR, "rust"), check=True, stdout=subprocess.DEVNULL)


def compare_trx(ref_path, test_path, name):
    print(f"\nValidating {name}...")
    ref = load(ref_path)
    test = load(test_path)

    # Check offsets
    if not np.array_equal(ref.streamlines._offsets, test.streamlines._offsets):
        print(f"  [FAILED] Offsets mismatch in {name}")
        return False
    if ref.streamlines._offsets.dtype != test.streamlines._offsets.dtype:
        print(f"  [WARNING] Offsets dtype mismatch in {name}: {ref.streamlines._offsets.dtype} != {test.streamlines._offsets.dtype}")

    # Check data (positions)
    if not np.allclose(ref.streamlines._data, test.streamlines._data, atol=1e-4):
        print(f"  [FAILED] Coordinates mismatch in {name}")
        return False
    if ref.streamlines._data.dtype != test.streamlines._data.dtype:
        print(f"  [WARNING] Coordinates dtype mismatch in {name}: {ref.streamlines._data.dtype} != {test.streamlines._data.dtype}")

    # Check header metadata
    if ref.header.get("NB_STREAMLINES") != test.header.get("NB_STREAMLINES"):
        print(f"  [FAILED] Header NB_STREAMLINES mismatch in {name}")
        return False

    # Check affine transformation
    if not np.allclose(ref.header.get("VOXEL_TO_RASMM"), test.header.get("VOXEL_TO_RASMM"), atol=1e-4):
        print(f"  [FAILED] Affine VOXEL_TO_RASMM mismatch in {name}")
        return False

    # Check dimensions
    if not np.array_equal(ref.header.get("DIMENSIONS"), test.header.get("DIMENSIONS")):
        print(f"  [FAILED] Dimensions mismatch in {name}")
        return False

    # Check data_per_vertex
    if set(ref.data_per_vertex.keys()) != set(test.data_per_vertex.keys()):
        print(f"  [FAILED] data_per_vertex keys mismatch in {name}")
        return False
    for k in ref.data_per_vertex.keys():
        if not np.allclose(ref.data_per_vertex[k]._data, test.data_per_vertex[k]._data, atol=1e-4):
            print(f"  [FAILED] DPV {k} data mismatch in {name}")
            return False
        if ref.data_per_vertex[k]._data.dtype != test.data_per_vertex[k]._data.dtype:
            print(f"  [WARNING] DPV {k} dtype mismatch in {name}")

    # Check data_per_streamline
    if set(ref.data_per_streamline.keys()) != set(test.data_per_streamline.keys()):
        print(f"  [FAILED] data_per_streamline keys mismatch in {name}")
        return False
    for k in ref.data_per_streamline.keys():
        if not np.allclose(ref.data_per_streamline[k], test.data_per_streamline[k], atol=1e-4):
            print(f"  [FAILED] DPS {k} data mismatch in {name}")
            return False
        if ref.data_per_streamline[k].dtype != test.data_per_streamline[k].dtype:
            print(f"  [WARNING] DPS {k} dtype mismatch in {name}")

    # Check groups
    if set(ref.groups.keys()) != set(test.groups.keys()):
        print(f"  [FAILED] groups keys mismatch in {name}: {list(ref.groups.keys())} != {list(test.groups.keys())}")
        return False
    for k in ref.groups.keys():
        if not np.array_equal(ref.groups[k], test.groups[k]):
            print(f"  [FAILED] Group {k} indices mismatch in {name}")
            return False
        if ref.groups[k].dtype != test.groups[k].dtype:
            print(f"  [WARNING] Group {k} dtype mismatch in {name}")

    # Check data_per_group
    for k in ref.groups.keys():
        ref_dpg = ref.data_per_group.get(k, {})
        test_dpg = test.data_per_group.get(k, {})
        if set(ref_dpg.keys()) != set(test_dpg.keys()):
            print(f"  [FAILED] DPG keys mismatch for group {k} in {name}")
            return False
        for d_k in ref_dpg.keys():
            if not np.allclose(ref_dpg[d_k], test_dpg[d_k], atol=1e-4):
                print(f"  [FAILED] DPG {d_k} mismatch for group {k} in {name}")
                return False
            if hasattr(ref_dpg[d_k], 'dtype') and hasattr(test_dpg[d_k], 'dtype'):
                if ref_dpg[d_k].dtype != test_dpg[d_k].dtype:
                    print(f"  [WARNING] DPG {d_k} dtype mismatch for group {k} in {name}")

    print(f"  [PASSED] {name} identical to gold standard.")
    return True


if __name__ == "__main__":
    print("Compiling C++...")
    subprocess.run(["cmake", "."], cwd=os.path.join(TEST_DIR, "cpp"), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["make"], cwd=os.path.join(TEST_DIR, "cpp"), check=True, stdout=subprocess.DEVNULL)
    print("Compiling Rust...")
    subprocess.run(["cargo", "build", "--release"], cwd=os.path.join(TEST_DIR, "rust"), check=True, stdout=subprocess.DEVNULL)

    trx_files = [f for f in os.listdir(TEST_DIR) if f.endswith(".trx") and not f.startswith("tmp_")]
    if not trx_files:
        print("No .trx files found to test.")
        sys.exit(0)

    all_passed = True
    for trx_file in trx_files:
        input_file = os.path.join(TEST_DIR, trx_file)
        run_tests_for_file(input_file)
        
        for lang in ["python", "js", "cpp", "rust"]:
            p = os.path.join(TEST_DIR, f"tmp_{lang}.trx")
            if not compare_trx(input_file, p, lang.upper()):
                all_passed = False

    if all_passed:
        print("\nALL LANGUAGES PASSED INTEGRITY TESTS ON ALL FILES.")
        sys.exit(0)
    else:
        print("\nSOME TESTS FAILED.")
        sys.exit(1)
