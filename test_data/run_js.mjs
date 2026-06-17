import fs from 'fs';
import path from 'path';
import { loadData, saveTRX } from '../js/utils.js';

async function main() {
    if (process.argv.length < 4) {
        process.exit(1);
    }
    let input_file = process.argv[2];
    let output_file = process.argv[3];
    let obj = await loadData(input_file);
    saveTRX(output_file, obj, path.basename(input_file));
}
main();
