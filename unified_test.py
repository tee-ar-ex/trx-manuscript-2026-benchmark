import os
import sys
import subprocess
import numpy as np

BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DIR = os.path.join(BENCH_DIR, "test_data")

# ---------------------------------------------------------------------------
# Helpers to load any format into a common representation for comparison
# ---------------------------------------------------------------------------


def load_as_arrays(filepath):
    """Load any supported tractography file and return (pts, offsets) as numpy arrays.

    Returns:
        pts: np.ndarray of shape (N, 3) — float32 or float64 coordinates
        offsets: np.ndarray of shape (M+1,) — cumulative point offsets (0-based)
    """
    ext = os.path.splitext(filepath)[1].lower()

    if ext == '.trx':
        from trx.trx_file_memmap import load as load_trx
        trx = load_trx(filepath)
        pts = np.array(trx.streamlines._data, dtype=np.float32)
        offsets = np.array(trx.streamlines._offsets, dtype=np.int64)
        # trx offsets are already cumulative with length = nb_streamlines+1
        if len(offsets) == trx.header.get("NB_STREAMLINES", len(offsets)):
            # offsets length equals nb_streamlines → need to append total
            total_pts = len(pts)
            offsets = np.append(offsets, total_pts)
        return pts, offsets

    elif ext in ('.trk', '.tck'):
        import nibabel as nib
        tractogram_file = nib.streamlines.load(filepath, lazy_load=False)
        tractogram = tractogram_file.tractogram
        streamlines = tractogram.streamlines
        pts = np.array(streamlines._data, dtype=np.float32)
        # Build cumulative offsets from lengths
        lengths = np.array(streamlines._lengths, dtype=np.int64)
        offsets = np.zeros(len(lengths) + 1, dtype=np.int64)
        offsets[1:] = np.cumsum(lengths)
        return pts, offsets

    elif ext == '.vtk':
        from fury.io import load_polydata
        from vtkmodules.util import numpy_support
        polydata = load_polydata(filepath)
        points_vtk = polydata.GetPoints().GetData()
        pts = np.array(numpy_support.vtk_to_numpy(points_vtk), dtype=np.float32)
        lines = polydata.GetLines()
        offsets_vtk = lines.GetOffsetsArray()
        if offsets_vtk is not None:
            offsets = np.array(numpy_support.vtk_to_numpy(offsets_vtk), dtype=np.int64)
        else:
            # Fallback: iterate cells
            lines.InitTraversal()
            from vtkmodules.vtkCommonCore import vtkIdList
            id_list = vtkIdList()
            offset_list = [0]
            while lines.GetNextCell(id_list):
                offset_list.append(offset_list[-1] + id_list.GetNumberOfIds())
            offsets = np.array(offset_list, dtype=np.int64)
        return pts, offsets

    else:
        raise ValueError(f"Unsupported format: {ext}")


# ---------------------------------------------------------------------------
# Runner dispatch — invoke each language's test binary
# ---------------------------------------------------------------------------

def run_tests_for_file(input_path, output_ext):
    """Run all 4 language test runners on input_path, saving as output_ext.

    Returns a dict {lang: True/False} indicating which runners succeeded.
    """
    print("======================================")
    print(f"Testing: {os.path.basename(input_path)} → *{output_ext}")
    print("======================================")

    ext_in = os.path.splitext(input_path)[1].lower()
    needs_ref = (ext_in in [".tck", ".vtk"]) and (output_ext in [".trx", ".trk"])
    ref_args = ["--ref", os.path.join(TEST_DIR, "fa.nii")] if needs_ref else []

    runners = {
        "python": [
            "python", os.path.join(TEST_DIR, "run_py.py"),
            input_path, os.path.join(TEST_DIR, f"tmp_python{output_ext}")
        ] + ref_args,
        "js": [
            "node", "--expose-gc", "--max-old-space-size=16384",
            os.path.join(TEST_DIR, "run_js.mjs"),
            input_path, os.path.join(TEST_DIR, f"tmp_js{output_ext}")
        ] + ref_args,
        "cpp": [
            "./test_cpp", input_path,
            os.path.join(TEST_DIR, f"tmp_cpp{output_ext}")
        ] + ref_args,
        "rust": [
            "cargo", "run", "--release", "--",
            input_path, os.path.join(TEST_DIR, f"tmp_rust{output_ext}")
        ] + ref_args,
    }

    print("Running JavaScript...")
    cwd_map = {
        "cpp": os.path.join(TEST_DIR, "cpp"),
        "rust": os.path.join(TEST_DIR, "rust"),
    }

    results = {}
    for lang, cmd in runners.items():
        print(f"Running {lang.upper()}...")
        try:
            kwargs = {"check": True}
            if lang in cwd_map:
                kwargs["cwd"] = cwd_map[lang]
            if lang == "rust":
                kwargs["stdout"] = subprocess.DEVNULL
            subprocess.run(cmd, **kwargs)
            results[lang] = True
        except subprocess.CalledProcessError as e:
            print(f"  [RUNNER ERROR] {lang.upper()} failed: {e}")
            results[lang] = False

    return results


# ---------------------------------------------------------------------------
# Comparison functions
# ---------------------------------------------------------------------------

def compare_trx(ref_path, test_path, name):
    """Full TRX comparison including metadata, DPV, DPS, groups."""
    from trx.trx_file_memmap import load as load_trx
    print(f"\nValidating {name}...")
    ref = load_trx(ref_path)
    test = load_trx(test_path)

    # Check offsets
    if not np.array_equal(ref.streamlines._offsets, test.streamlines._offsets):
        print(f"  [FAILED] Offsets mismatch in {name}")
        return False
    if ref.streamlines._offsets.dtype != test.streamlines._offsets.dtype:
        print(
            f"  [WARNING] Offsets dtype mismatch in {name}: {ref.streamlines._offsets.dtype} != {test.streamlines._offsets.dtype}")

    # Check data (positions)
    if not np.allclose(ref.streamlines._data, test.streamlines._data, atol=1e-4):
        print(f"  [FAILED] Coordinates mismatch in {name}")
        return False
    if ref.streamlines._data.dtype != test.streamlines._data.dtype:
        print(
            f"  [WARNING] Coordinates dtype mismatch in {name}: {ref.streamlines._data.dtype} != {test.streamlines._data.dtype}")

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
        print(
            f"  [FAILED] groups keys mismatch in {name}: {list(ref.groups.keys())} != {list(test.groups.keys())}")
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
                    print(
                        f"  [WARNING] DPG {d_k} dtype mismatch for group {k} in {name}")

    print(f"  [PASSED] {name} identical to gold standard.")
    return True


def compare_legacy(ref_path, test_path, name):
    """Compare two legacy-format files (TRK, TCK, VTK) by loading both into
    numpy arrays and checking streamline count + coordinate parity."""
    print(f"\nValidating {name}...")

    try:
        ref_pts, ref_offsets = load_as_arrays(ref_path)
        test_pts, test_offsets = load_as_arrays(test_path)
    except Exception as e:
        print(f"  [FAILED] Could not load files for {name}: {e}")
        return False

    # Check number of streamlines
    ref_nb = len(ref_offsets) - 1
    test_nb = len(test_offsets) - 1
    if ref_nb != test_nb:
        print(f"  [FAILED] Streamline count mismatch in {name}: {ref_nb} != {test_nb}")
        return False

    # Check total point count
    if len(ref_pts) != len(test_pts):
        print(f"  [FAILED] Total point count mismatch in {name}: {len(ref_pts)} != {len(test_pts)}")
        return False

    # Check offsets
    if not np.array_equal(ref_offsets, test_offsets):
        print(f"  [FAILED] Offsets mismatch in {name}")
        return False

    # Check coordinates
    if not np.allclose(ref_pts, test_pts, atol=1e-4):
        max_diff = np.max(np.abs(ref_pts - test_pts))
        print(f"  [FAILED] Coordinates mismatch in {name} (max diff: {max_diff:.6f})")
        return False

    print(f"  [PASSED] {name} identical to gold standard.")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Compile C++ and Rust test harnesses
    print("Compiling C++...")
    subprocess.run(["cmake", "."], cwd=os.path.join(
        TEST_DIR, "cpp"), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["make"], cwd=os.path.join(TEST_DIR, "cpp"),
                   check=True, stdout=subprocess.DEVNULL)
    print("Compiling Rust...")
    subprocess.run(["cargo", "build", "--release"], cwd=os.path.join(TEST_DIR,
                   "rust"), check=True, stdout=subprocess.DEVNULL)

    # 2. Discover gold standard test files
    FORMATS = {
        ".trx": "compare_trx",
        ".trk": "compare_legacy",
        ".tck": "compare_legacy",
        ".vtk": "compare_legacy",
    }

    all_passed = True

    # --- TRX tests (full metadata comparison) ---
    trx_files = sorted([f for f in os.listdir(TEST_DIR)
                        if f.endswith(".trx") and not f.startswith("tmp_") and not f.startswith("relay")])
    for trx_file in trx_files:
        input_file = os.path.join(TEST_DIR, trx_file)
        runner_results = run_tests_for_file(input_file, ".trx")

        for lang in ["python", "js", "cpp", "rust"]:
            if not runner_results.get(lang, False):
                print(f"\n  [SKIPPED] {lang.upper()} (.trx) — runner failed")
                all_passed = False
                continue
            p = os.path.join(TEST_DIR, f"tmp_{lang}.trx")
            if not compare_trx(input_file, p, f"{lang.upper()} (.trx)"):
                all_passed = False

    # --- Legacy format tests (TRK, TCK, VTK) ---
    for ext in [".trk", ".tck", ".vtk"]:
        legacy_files = sorted([f for f in os.listdir(TEST_DIR)
                               if f.endswith(ext) and not f.startswith("tmp_") and not f.startswith("relay")])
        for legacy_file in legacy_files:
            input_file = os.path.join(TEST_DIR, legacy_file)
            runner_results = run_tests_for_file(input_file, ext)

            for lang in ["python", "js", "cpp", "rust"]:
                if not runner_results.get(lang, False):
                    print(f"\n  [SKIPPED] {lang.upper()} ({ext}) — runner failed")
                    all_passed = False
                    continue
                p = os.path.join(TEST_DIR, f"tmp_{lang}{ext}")
                if not compare_legacy(input_file, p, f"{lang.upper()} ({ext})"):
                    all_passed = False

    # 4. Cleanup
    print("\nCleaning up intermediary tmp files...")
    import glob
    import shutil
    for f in glob.glob(os.path.join(TEST_DIR, "tmp_*.*")):
        try:
            if os.path.isdir(f):
                shutil.rmtree(f)
            else:
                os.remove(f)
        except BaseException:
            pass

    if all_passed:
        print("\n" + "=" * 60)
        print("ALL LANGUAGES PASSED INTEGRITY TESTS ON ALL FORMATS.")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("SOME TESTS FAILED.")
        print("=" * 60)
        sys.exit(1)
