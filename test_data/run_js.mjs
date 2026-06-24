import fs from 'fs';
import path from 'path';
import { loadData, saveTRX, saveTRK, saveTCK, saveVTK, readNiftiHeader } from '../js/utils.js';

async function main() {
    let args = process.argv.slice(2);
    let refPath = null;
    let input_file = null;
    let output_file = null;

    for (let i = 0; i < args.length; i++) {
        if (args[i] === '--ref' && i + 1 < args.length) {
            refPath = args[i + 1];
            i++;
        } else if (!input_file) {
            input_file = args[i];
        } else if (!output_file) {
            output_file = args[i];
        }
    }

    if (!input_file || !output_file) {
        process.exit(1);
    }

    if (!fs.existsSync(input_file)) {
        console.error(`Error: input file not found: ${input_file}`);
        process.exit(1);
    }

    let inExt = path.extname(input_file).toLowerCase();
    let ext = path.extname(output_file).toLowerCase();

    let refHeader = null;
    if ((inExt === '.tck' || inExt === '.vtk') && (ext === '.trx' || ext === '.trk')) {
        if (!refPath) {
            console.error("Error: --ref <nifti_path> is required when converting from TCK/VTK to TRX/TRK");
            process.exit(1);
        }
        if (!fs.existsSync(refPath)) {
            console.error(`Error: reference file not found: ${refPath}`);
            process.exit(1);
        }
        refHeader = readNiftiHeader(refPath);
    }

    let obj = await loadData(input_file);

    if (ext === '.trx') {
        saveTRX(output_file, obj, path.basename(input_file), refHeader);
    } else if (ext === '.trk') {
        saveTRK(output_file, obj, path.basename(input_file), refHeader);
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
