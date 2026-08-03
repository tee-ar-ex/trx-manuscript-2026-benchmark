import itertools
import os
import subprocess
import numpy as np
from trx.trx_file_memmap import load as load_trx
from trx.trx_file_memmap import save as save_trx


def run_cmd(cmd):
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def get_runner(lang):
    if lang == "py":
        return ["python3", "test_data/run_py.py"]
    if lang == "rs":
        return ["test_data/rust/target/release/test_rust"]
    if lang == "cpp":
        return ["test_data/cpp/test_cpp"]
    if lang == "js":
        return ["node", "test_data/run_js.mjs"]


def test_language_relay():
    print("\n--- Running Test 1: Language Relay (All Combinations) ---")
    gs_file = "test_data/f32_ui32_w_metadata.trx"
    t_orig = load_trx(gs_file)
    langs = ["py", "rs", "cpp", "js"]
    failed = 0
    total = 0
    for perm in itertools.permutations(langs):
        total += 1
        print(f"\nPermutation {total}/24: {' -> '.join(perm)}")
        current_input = gs_file

        for lang in perm:
            out_file = f"test_data/relay_tmp_{lang}.trx"
            cmd = get_runner(lang) + [current_input, out_file]
            ext_in = os.path.splitext(current_input)[1].lower()
            if ext_in in [".tck", ".vtk"]:
                cmd += ["--ref", "test_data/fa.nii"]
            run_cmd(cmd)
            current_input = out_file

        t_final = load_trx(current_input)
        if np.allclose(t_orig.streamlines._data, t_final.streamlines._data, atol=1e-3):
            print(f"[PASSED] Combination {' -> '.join(perm)}")
        else:
            print(f"[FAILED] Combination {' -> '.join(perm)}: Coordinates drifted!")
            failed += 1

    if failed == 0:
        print("\n[SUCCESS] All 24 language relay permutations passed without coordinate drift!")
    else:
        print(f"\n[ERROR] {failed}/24 permutations failed.")


def get_rasmm(trx_obj):
    pts = trx_obj.streamlines._data
    affine = trx_obj.header.get("VOXEL_TO_RASMM", np.eye(4))
    if affine is None:
        affine = np.eye(4)
    # Apply affine
    pts_homo = np.hstack([pts, np.ones((pts.shape[0], 1))])
    pts_rasmm = (affine @ pts_homo.T).T[:, :3]
    return pts_rasmm


def test_format_relay():
    print("\n--- Running Test 2: Format Relay ---")
    gs_file = "test_data/f32_ui32_w_metadata.trx"
    out_trk = "test_data/relay.trk"
    out_tck = "test_data/relay.tck"
    out_trx = "test_data/relay_format.trx"

    # Convert TRX -> TRK (via JS)
    print("TRX -> TRK (via JS)")
    run_cmd(["node", "test_data/run_js.mjs", gs_file, out_trk])

    # Convert TRK -> TCK (via C++)
    print("TRK -> TCK (via C++)")
    run_cmd(["test_data/cpp/test_cpp", out_trk, out_tck])

    # Convert TCK -> TRX (via Rust)
    print("TCK -> TRX (via Rust)")
    run_cmd(["test_data/rust/target/release/test_rust", out_tck, out_trx, "--ref", "test_data/fa.nii"])

    # Validate output in RASMM space
    t_orig = load_trx(gs_file)
    t_final = load_trx(out_trx)

    orig_rasmm = get_rasmm(t_orig)
    final_rasmm = get_rasmm(t_final)

    if np.allclose(orig_rasmm, final_rasmm, atol=1e-3):
        print("[PASSED] Format Relay: RASMM coordinates maintained across formats!")
    else:
        max_drift = np.max(np.abs(orig_rasmm - final_rasmm))
        print(f"[FAILED] Format Relay: Coordinates drifted by {max_drift:.5f} mm!")


def test_precision_relay():
    print("\n--- Running Test 3: Precision Relay ---")
    gs_file = "test_data/f32_ui32_w_metadata.trx"
    out_f32 = "test_data/relay_p32.trx"
    out_f16 = "test_data/relay_p16.trx"

    t_orig = load_trx(gs_file)
    # Save as float32
    t_orig.header["DATA_TYPE"] = "float32"
    save_trx(t_orig, out_f32)

    # Python script to downcast to float16
    script_f16 = "test_data/tmp_f16.py"
    with open(script_f16, "w") as f:
        f.write(f"""
from trx.trx_file_memmap import load, save
import numpy as np
t = load('{out_f32}')
t.streamlines._data = t.streamlines._data.astype(np.float16)
t.header['DATA_TYPE'] = 'float16'
save(t, '{out_f16}')
""")
    run_cmd(["python3", script_f16])

    t_f16 = load_trx(out_f16)
    max_diff = np.max(np.abs(t_orig.streamlines._data.astype(np.float32) - t_f16.streamlines._data.astype(np.float32)))
    print(f"[PASSED] Precision Relay: Downcasting f32->f16 -> Max coordinate drift: {max_diff:.5f} mm")


def test_metadata_relay():
    print("\n--- Running Test 4: Metadata Relay ---")
    gs_file = "test_data/f32_ui32_w_metadata.trx"
    out_py = "test_data/relay_meta_py.trx"
    out_rs = "test_data/relay_meta_rs.trx"
    out_cpp = "test_data/relay_meta_cpp.trx"
    out_js = "test_data/relay_meta_js.trx"

    print("Pass via Python...")
    run_cmd(["python3", "test_data/run_py.py", gs_file, out_py])

    print("Pass via Rust...")
    run_cmd(["test_data/rust/target/release/test_rust", out_py, out_rs])

    print("Pass via C++...")
    run_cmd(["test_data/cpp/test_cpp", out_rs, out_cpp])

    print("Pass via JS...")
    run_cmd(["node", "test_data/run_js.mjs", out_cpp, out_js])

    t_orig = load_trx(gs_file)
    t_final = load_trx(out_js)

    orig_keys = set(t_orig.header.keys())
    final_keys = set(t_final.header.keys())
    if orig_keys == final_keys:
        print("[PASSED] Metadata Relay: All header keys preserved across Python, Rust, C++, and JS!")
    else:
        print(f"[FAILED] Metadata Relay: Keys drifted! Orig: {orig_keys}, Final: {final_keys}")


if __name__ == "__main__":
    test_language_relay()
    test_format_relay()
    test_precision_relay()
    test_metadata_relay()
    print("\nAll relay tests finished.")

    print("\nCleaning up intermediary relay files...")
    import glob
    import shutil
    for f in glob.glob("test_data/relay*.*") + glob.glob("test_data/tmp*.*"):
        try:
            if os.path.isdir(f):
                shutil.rmtree(f)
            else:
                os.remove(f)
        except Exception:
            pass
