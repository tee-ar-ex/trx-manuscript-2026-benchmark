import os
import trx.trx_file_memmap as trx_mmap
from nibabel.streamlines.tractogram import Tractogram

filepath = "empty_test.trx"
tractogram = Tractogram(streamlines=[])
trx = trx_mmap.TrxFile.from_tractogram(tractogram, reference="fa.nii")
trx_mmap.save(trx, filepath)

import zipfile
with zipfile.ZipFile(filepath, "r") as zf:
    print(zf.namelist())
