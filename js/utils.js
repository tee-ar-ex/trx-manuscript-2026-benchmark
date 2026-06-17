import fs from 'fs';
import * as path from 'path';
import { readTRK, readTCK, readVTK, readTRX } from '../../trx-javascript/streamlineIO.mjs';
import { execSync } from 'child_process';
import * as fflate from 'fflate';

/**
 * Force OS page cache eviction for the data file.
 * We use python3 to call posix_fadvise programmatically on Linux.
 */
export function evictFromCache(filename) {
    try {
        const stats = fs.statSync(filename);
        const size = stats.size;
        execSync(`python3 -c "import os; fd = os.open('${filename}', os.O_RDONLY); os.posix_fadvise(fd, 0, ${size}, 4); os.close(fd)"`);
    } catch (e) {
        console.error(`      [WARN] Cache eviction failed for ${filename}: ${e.message}`);
    }
}

/**
 * Force garbage collection if Node is run with --expose-gc flag.
 */
export function releaseMemory() {
    if (global && global.gc) {
        global.gc();
    }
}

/**
 * Load tractography data file based on its extension.
 */
export async function loadData(filepath) {
    const ext = path.extname(filepath).toLowerCase();
    if (ext === '.trx') {
        return await readTRX(filepath, true);
    } else {
        const stats = fs.statSync(filepath);
        const size = stats.size;
        let arrayBuffer;

        if (size >= 2 * 1024 * 1024 * 1024) {
            arrayBuffer = new ArrayBuffer(size);
            const uint8Array = new Uint8Array(arrayBuffer);
            const fd = fs.openSync(filepath, 'r');
            const chunkSize = 512 * 1024 * 1024;
            let offset = 0;
            while (offset < size) {
                const bytesToRead = Math.min(chunkSize, size - offset);
                const bytesRead = fs.readSync(fd, uint8Array, offset, bytesToRead, offset);
                if (bytesRead === 0) break;
                offset += bytesRead;
            }
            fs.closeSync(fd);
        } else {
            const buf = fs.readFileSync(filepath);
            arrayBuffer = buf.buffer;
            if (buf.byteOffset !== 0 || buf.byteLength !== buf.buffer.byteLength) {
                arrayBuffer = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
            }
        }

        if (ext === '.tck') {
            return readTCK(arrayBuffer);
        } else if (ext === '.vtk') {
            return readVTK(arrayBuffer);
        } else if (ext === '.trk') {
            return readTRK(arrayBuffer);
        } else {
            throw new Error(`Unsupported extension ${ext}`);
        }
    }
}

// Fast float32 to float16 conversion
function encodeFloat16(val) {
    const floatView = new Float32Array(1);
    const int32View = new Int32Array(floatView.buffer);
    floatView[0] = val;
    const f = int32View[0];
    
    const sign = (f >> 16) & 0x8000;
    let exponent = ((f >> 23) & 0xff) - 127;
    let mantissa = f & 0x007fffff;
    
    if (exponent <= -15) {
        if (exponent < -24) {
            return sign; // underflow
        }
        mantissa = (mantissa | 0x00800000) >> (-14 - exponent);
        return sign | (mantissa >> 13);
    } else if (exponent >= 16) {
        return sign | 0x7c00; // overflow to infinity
    }
    
    return sign | ((exponent + 15) << 10) | (mantissa >> 13);
}

function float32ToFloat16(float32Array) {
    const out = new Uint16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
        out[i] = encodeFloat16(float32Array[i]);
    }
    return out;
}

function buildTckHeader(numStreamlines) {
    let offset = 80;
    while (true) {
        let h = `mrtrix tracks\ncount: ${String(numStreamlines).padStart(10, '0')}\ndatatype: Float32LE\nfile: . ${offset}\nEND\n`;
        if (h.length <= offset) {
            return h.padEnd(offset, ' ');
        }
        offset = h.length;
    }
}

export function saveTCK(filepath, obj) {
    const fd = fs.openSync(filepath, 'w');
    const numStreamlines = obj.offsetPt0.length - 1;
    const header = buildTckHeader(numStreamlines);
    fs.writeSync(fd, header);

    const chunkSize = 16 * 1024 * 1024; // 16MB buffer
    const buf = new ArrayBuffer(chunkSize);
    const view = new DataView(buf);
    const u8View = new Uint8Array(buf);

    let bufOffset = 0;
    const pts = obj.pts;
    const offsets = obj.offsetPt0;

    for (let i = 0; i < numStreamlines; i++) {
        const start = offsets[i];
        const end = offsets[i+1];
        
        for (let j = start; j < end; j++) {
            if (bufOffset + 12 > chunkSize) {
                fs.writeSync(fd, u8View, 0, bufOffset);
                bufOffset = 0;
            }
            view.setFloat32(bufOffset, pts[j*3], true);
            view.setFloat32(bufOffset + 4, pts[j*3 + 1], true);
            view.setFloat32(bufOffset + 8, pts[j*3 + 2], true);
            bufOffset += 12;
        }
        if (bufOffset + 12 > chunkSize) {
            fs.writeSync(fd, u8View, 0, bufOffset);
            bufOffset = 0;
        }
        view.setFloat32(bufOffset, NaN, true);
        view.setFloat32(bufOffset + 4, NaN, true);
        view.setFloat32(bufOffset + 8, NaN, true);
        bufOffset += 12;
    }

    if (bufOffset + 12 > chunkSize) {
        fs.writeSync(fd, u8View, 0, bufOffset);
        bufOffset = 0;
    }
    view.setFloat32(bufOffset, Infinity, true);
    view.setFloat32(bufOffset + 4, Infinity, true);
    view.setFloat32(bufOffset + 8, Infinity, true);
    bufOffset += 12;

    if (bufOffset > 0) {
        fs.writeSync(fd, u8View, 0, bufOffset);
    }
    fs.closeSync(fd);
}

export function saveTRK(filepath, obj, originalFilename) {
    const fd = fs.openSync(filepath, 'w');
    const headerBytes = new Uint8Array(1000);
    const view = new DataView(headerBytes.buffer);

    headerBytes.set([84, 82, 65, 67, 75], 0);

    let dim = [256, 256, 256];
    let voxelSize = [1, 1, 1];
    let voxToRas = [
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1]
    ];

    if (obj.header) {
        if (obj.header.DIMENSIONS) dim = obj.header.DIMENSIONS;
        if (obj.header.VOXEL_TO_RASMM) {
            voxToRas = obj.header.VOXEL_TO_RASMM;
            voxelSize = [
                Math.sqrt(voxToRas[0][0]**2 + voxToRas[1][0]**2 + voxToRas[2][0]**2),
                Math.sqrt(voxToRas[0][1]**2 + voxToRas[1][1]**2 + voxToRas[2][1]**2),
                Math.sqrt(voxToRas[0][2]**2 + voxToRas[1][2]**2 + voxToRas[2][2]**2)
            ];
        }
    }

    view.setInt16(6, dim[0], true);
    view.setInt16(8, dim[1], true);
    view.setInt16(10, dim[2], true);

    view.setFloat32(12, voxelSize[0], true);
    view.setFloat32(16, voxelSize[1], true);
    view.setFloat32(20, voxelSize[2], true);

    let off = 440;
    for (let r = 0; r < 4; r++) {
        for (let c = 0; c < 4; c++) {
            view.setFloat32(off, voxToRas[r][c], true);
            off += 4;
        }
    }

    headerBytes.set([82, 65, 83, 0], 948);

    const numStreamlines = obj.offsetPt0.length - 1;
    view.setInt32(988, numStreamlines, true);
    view.setInt32(992, 2, true);
    view.setInt32(996, 1000, true);

    fs.writeSync(fd, headerBytes);

    const chunkSize = 16 * 1024 * 1024;
    const buf = new ArrayBuffer(chunkSize);
    const payloadView = new DataView(buf);
    const u8View = new Uint8Array(buf);

    let bufOffset = 0;
    const pts = obj.pts;
    const offsets = obj.offsetPt0;

    for (let i = 0; i < numStreamlines; i++) {
        const start = offsets[i];
        const end = offsets[i+1];
        const n_pts = end - start;

        if (bufOffset + 4 > chunkSize) {
            fs.writeSync(fd, u8View, 0, bufOffset);
            bufOffset = 0;
        }
        payloadView.setInt32(bufOffset, n_pts, true);
        bufOffset += 4;

        for (let j = start; j < end; j++) {
            if (bufOffset + 12 > chunkSize) {
                fs.writeSync(fd, u8View, 0, bufOffset);
                bufOffset = 0;
            }
            payloadView.setFloat32(bufOffset, pts[j*3], true);
            payloadView.setFloat32(bufOffset + 4, pts[j*3 + 1], true);
            payloadView.setFloat32(bufOffset + 8, pts[j*3 + 2], true);
            bufOffset += 12;
        }
    }

    if (bufOffset > 0) {
        fs.writeSync(fd, u8View, 0, bufOffset);
    }
    fs.closeSync(fd);
}

export function saveVTK(filepath, obj) {
    const fd = fs.openSync(filepath, 'w');
    const numStreamlines = obj.offsetPt0.length - 1;
    const numPoints = obj.pts.length / 3;

    const header = `# vtk DataFile Version 3.0\nvtk output\nBINARY\nDATASET POLYDATA\nPOINTS ${numPoints} float\n`;
    fs.writeSync(fd, header);

    const pts = obj.pts;
    const offsets = obj.offsetPt0;

    const chunkSize = 16 * 1024 * 1024;
    const buf = new ArrayBuffer(chunkSize);
    const view = new DataView(buf);
    const u8View = new Uint8Array(buf);

    let bufOffset = 0;
    for (let i = 0; i < numPoints; i++) {
        if (bufOffset + 12 > chunkSize) {
            fs.writeSync(fd, u8View, 0, bufOffset);
            bufOffset = 0;
        }
        view.setFloat32(bufOffset, pts[i*3], false); // Big endian
        view.setFloat32(bufOffset + 4, pts[i*3 + 1], false);
        view.setFloat32(bufOffset + 8, pts[i*3 + 2], false);
        bufOffset += 12;
    }
    if (bufOffset > 0) {
        fs.writeSync(fd, u8View, 0, bufOffset);
        bufOffset = 0;
    }

    const cellArraySize = numStreamlines + numPoints;
    const linesHeader = `LINES ${numStreamlines} ${cellArraySize}\n`;
    fs.writeSync(fd, linesHeader);

    for (let i = 0; i < numStreamlines; i++) {
        const start = offsets[i];
        const end = offsets[i+1];
        const n_pts = end - start;

        if (bufOffset + 4 > chunkSize) {
            fs.writeSync(fd, u8View, 0, bufOffset);
            bufOffset = 0;
        }
        view.setInt32(bufOffset, n_pts, false); // Big endian
        bufOffset += 4;

        for (let j = start; j < end; j++) {
            if (bufOffset + 4 > chunkSize) {
                fs.writeSync(fd, u8View, 0, bufOffset);
                bufOffset = 0;
            }
            view.setInt32(bufOffset, j, false);
            bufOffset += 4;
        }
    }
    if (bufOffset > 0) {
        fs.writeSync(fd, u8View, 0, bufOffset);
    }
    fs.closeSync(fd);
}

export function saveTRX(filepath, obj, originalFilename) {
    let dtype = obj.positions_dtype || "float32";
    let ptsData = obj.pts;
    if (ptsData instanceof Float64Array) {
        dtype = "float64";
    }

    if (originalFilename.includes("f16") || dtype === "float16") {
        dtype = "float16";
        ptsData = float32ToFloat16(obj.pts);
    } else if (originalFilename.includes("f64")) {
        dtype = "float64";
        ptsData = new Float64Array(obj.pts);
    }

    const numStreamlines = obj.offsetPt0.length - 1;
    const numPoints = obj.pts.length / 3;

    let header = {
        "VOXEL_TO_RASMM": [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ],
        "DIMENSIONS": [256, 256, 256],
        "NB_STREAMLINES": numStreamlines,
        "NB_VERTICES": numPoints
    };

    if (obj.header) {
        header.VOXEL_TO_RASMM = obj.header.VOXEL_TO_RASMM || header.VOXEL_TO_RASMM;
        header.DIMENSIONS = obj.header.DIMENSIONS || header.DIMENSIONS;
    }

    const zipObj = {};
    zipObj["header.json"] = fflate.strToU8(JSON.stringify(header, null, 4));
    zipObj[`positions.3.${dtype}`] = new Uint8Array(ptsData.buffer, ptsData.byteOffset, ptsData.byteLength);
    
    let offsetDtype = "uint32";
    let offsetData = obj.offsetPt0.subarray(0, numStreamlines + 1);
    if (originalFilename.includes("ui64")) {
        offsetDtype = "uint64";
        const u64Bytes = new Uint8Array((numStreamlines + 1) * 8);
        const view = new DataView(u64Bytes.buffer);
        for (let i = 0; i <= numStreamlines; i++) {
            view.setUint32(i * 8, offsetData[i], true);
            view.setUint32(i * 8 + 4, 0, true);
        }
        zipObj[`offsets.${offsetDtype}`] = u64Bytes;
    } else {
        zipObj[`offsets.${offsetDtype}`] = new Uint8Array(offsetData.buffer, offsetData.byteOffset, offsetData.byteLength);
    }
    
    function getDtypeExt(vals) {
        if (vals instanceof Float64Array) return 'float64';
        if (vals instanceof Float32Array) return 'float32';
        if (vals instanceof Uint32Array) return 'uint32';
        if (vals instanceof Int32Array) return 'int32';
        if (vals instanceof Uint16Array) return 'uint16';
        if (vals instanceof Int16Array) return 'int16';
        if (vals instanceof Uint8Array) return 'uint8';
        if (vals instanceof Int8Array) return 'int8';
        return 'float32';
    }

    function getCorrectFname(prop) {
        let name = prop.fname || prop.id;
        let parts = name.split('.');
        let ext = getDtypeExt(prop.vals);
        if (parts.length >= 2) {
            parts[parts.length - 1] = ext;
            return parts.join('.');
        }
        return name + '.' + ext;
    }

    if (obj.dpv) {
        for (let prop of obj.dpv) {
            zipObj[`dpv/${getCorrectFname(prop)}`] = new Uint8Array(prop.vals.buffer, prop.vals.byteOffset, prop.vals.byteLength);
        }
    }
    if (obj.dps) {
        for (let prop of obj.dps) {
            zipObj[`dps/${getCorrectFname(prop)}`] = new Uint8Array(prop.vals.buffer, prop.vals.byteOffset, prop.vals.byteLength);
        }
    }
    if (obj.dpg) {
        for (let prop of obj.dpg) {
            zipObj[`dpg/${getCorrectFname(prop)}`] = new Uint8Array(prop.vals.buffer, prop.vals.byteOffset, prop.vals.byteLength);
        }
    }
    if (obj.groups) {
        for (let prop of obj.groups) {
            zipObj[`groups/${getCorrectFname(prop)}`] = new Uint8Array(prop.vals.buffer, prop.vals.byteOffset, prop.vals.byteLength);
        }
    }

    const zipped = fflate.zipSync(zipObj);
    fs.writeFileSync(filepath, zipped);
}
