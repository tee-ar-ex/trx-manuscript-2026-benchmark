import fs from 'fs';
import path from 'path';
import { loadData, saveTRX, saveTRK, saveTCK, saveVTK } from '../js/utils.js';

async function main() {
    if (process.argv.length < 4) {
        process.exit(1);
    }
    let input_file = process.argv[2];
    let output_file = process.argv[3];
    let obj = await loadData(input_file);
    let ext = path.extname(output_file).toLowerCase();

    if (ext === '.trx') {
        saveTRX(output_file, obj, path.basename(input_file));
    } else if (ext === '.trk') {
        saveTRK(output_file, obj, path.basename(input_file));
    } else if (ext === '.tck') {
        saveTCK(output_file, obj);
    } else if (ext === '.vtk') {
        saveVTK(output_file, obj);
    } else {
        console.error(`Unsupported format: ${ext}`);
        process.exit(1);
    }
}
main();
