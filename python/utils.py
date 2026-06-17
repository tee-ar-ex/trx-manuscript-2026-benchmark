import ctypes
import gc
import os
from time import sleep

import nibabel as nib
import numpy as np
from fury import io
from trx.trx_file_memmap import load as load_trx
from vtk.util import numpy_support

# Forcing the C library to return memory to the OS (Linux only)
try:
    libc = ctypes.CDLL("libc.so.6")
except Exception:
    libc = None


def release_memory():
    """Force Python garbage collection and libc heap trimming."""
    gc.collect()
    if libc:
        # 0 means return as much as possible to the OS
        libc.malloc_trim(0)
    sleep(1)


def evict_from_cache(filename):
    """Force OS page cache eviction for the data file."""
    try:
        fd = os.open(filename, os.O_RDONLY)
        os.posix_fadvise(fd, 0, os.path.getsize(
            filename), 4)  # 4 = POSIX_FADV_DONTNEED
        os.close(fd)
        sleep(1)
    except Exception as e:
        print(f"      [WARN] Cache eviction failed for {filename}: {e}")


def load_vtk_as_tractogram(filename):
    polydata = io.load_polydata(filename)

    if polydata is None or polydata.GetNumberOfPoints() == 0:
        raise ValueError(f"File {filename} is invalid or contains no points.")

    if polydata.GetNumberOfLines() == 0:
        raise ValueError(f"File {filename} contains no lines (streamlines).")

    # 1. Extract raw buffers from VTK
    points_vtk = polydata.GetPoints().GetData()
    lines = polydata.GetLines()
    if points_vtk is None or lines is None:
        raise ValueError(f"Could not extract points or lines from {filename}")

    offsets_vtk = lines.GetOffsetsArray()
    conn_vtk = lines.GetConnectivityArray()

    if offsets_vtk is None or conn_vtk is None:
        raise ValueError(
            f"Direct access to offsets/connectivity not available for {filename}. "
            "This function requires VTK 9.0+ style PolyData.")

    points = numpy_support.vtk_to_numpy(points_vtk)
    offsets = numpy_support.vtk_to_numpy(offsets_vtk)
    connectivity = numpy_support.vtk_to_numpy(conn_vtk)

    # 2. Reorder points if connectivity is not trivial (identity mapping)
    # This ensures that PointData (dpp) and streamlines remain aligned.
    if not np.all(
        connectivity == np.arange(
            len(connectivity),
            dtype=connectivity.dtype)):
        points = points[connectivity]
        reorder_point_data = True
    else:
        reorder_point_data = False

    # 3. Prepare nibabel-style offsets and lengths
    # nibabel expects int64 for these internal attributes
    nib_offsets = offsets[:-1].astype(np.int64)
    lengths = np.diff(offsets).astype(np.int64)

    # 4. Fast-initialize ArraySequence for streamlines
    streamlines = nib.streamlines.ArraySequence()
    streamlines._data = points
    streamlines._offsets = nib_offsets
    streamlines._lengths = lengths

    # 5. Fast-initialize PointData (dpp)
    dpp = {}
    point_data = polydata.GetPointData()
    num_expected_points = len(connectivity)

    for i in range(point_data.GetNumberOfArrays()):
        name = point_data.GetArrayName(i)
        data = numpy_support.vtk_to_numpy(point_data.GetArray(i))

        # Only include metadata that matches the point count
        if len(data) == num_expected_points:
            if reorder_point_data:
                data = data[connectivity]
            as_obj = nib.streamlines.ArraySequence()
            as_obj._data = data
            as_obj._offsets = nib_offsets
            as_obj._lengths = lengths
            dpp[name] = as_obj

    # 6. Extract CellData (dps)
    dps = {}
    cell_data = polydata.GetCellData()
    num_cells = polydata.GetNumberOfLines()
    for i in range(cell_data.GetNumberOfArrays()):
        name = cell_data.GetArrayName(i)
        data = numpy_support.vtk_to_numpy(cell_data.GetArray(i))

        # Only include metadata that matches the cell count
        if len(data) == num_cells:
            dps[name] = data

    return nib.streamlines.Tractogram(
        streamlines,
        data_per_point=dpp,
        data_per_streamline=dps)


def load_data(filename):
    _, ext = os.path.splitext(filename)
    if ext in [".trk", ".tck"]:
        obj = nib.streamlines.load(filename, lazy_load=False)
    elif ext in [".vtk", ".vtp", ".fib"]:
        obj = io.load_polydata(filename)
    elif ext == ".trx":
        obj = load_trx(filename)
        obj.to_memory()
        obj.streamlines._data = obj.streamlines._data.astype(np.float32)
    else:
        raise ValueError(f"Unsupported extension {ext}")

    return obj
