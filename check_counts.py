import os
import sys
import numpy as np
import nibabel as nib
from fury import io

# Ensure local python directory is in import path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.utils import load_data, load_vtk_as_tractogram

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
        print("Error: TRX_BENCHMARK_DATA_DIR not set.")
        sys.exit(1)
        
    for filename in FILENAMES:
        path = os.path.join(data_dir, filename)
        if not os.path.exists(path):
            print(f"{filename}: Missing")
            continue
        try:
            obj = load_data(path)
            s_count, p_count = get_counts(obj)
            print(f"{filename}: streamlines={s_count}, points={p_count}")
        except Exception as e:
            print(f"{filename}: Failed to load ({e})")

if __name__ == "__main__":
    main()
