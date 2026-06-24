import fs from 'fs';
import * as path from 'path';
import { readTRK, readTCK, readVTK, readTRX } from '../../trx-javascript/streamlineIO.mjs';
import { execSync } from 'child_process';
import * as fflate from 'fflate';
import { mat4, vec3 } from '../../trx-javascript/node_modules/gl-matrix/esm/index.js';

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

export { saveTCK, saveTRK, saveVTK, saveTRX, readNiftiHeader } from '../../trx-javascript/streamlineIO.mjs';
