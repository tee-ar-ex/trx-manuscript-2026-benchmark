import sys
import os

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    ext = os.path.splitext(input_file)[1].lower()

    if ext == '.trx':
        from trx.trx_file_memmap import load, save
        t = load(input_file)
        save(t, output_file)
    elif ext in ('.trk', '.tck'):
        import nibabel as nib
        tractogram_file = nib.streamlines.load(input_file, lazy_load=False)
        nib.streamlines.save(tractogram_file.tractogram, output_file)
    elif ext == '.vtk':
        from fury.io import load_polydata, save_polydata
        polydata = load_polydata(input_file)
        save_polydata(polydata, output_file, binary=True)
    else:
        print(f"Unsupported format: {ext}")
        sys.exit(1)
