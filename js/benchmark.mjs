import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { evictFromCache, releaseMemory, loadData, saveTRK, saveTCK, saveVTK, saveTRX } from './utils.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const FILENAMES = [
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
];

const EXPECTED_POINTS = 201521017;
const MIN_EXPECTED_STREAMLINES = 5979090;
const MAX_EXPECTED_STREAMLINES = 5979100;

function calculateMean(array) {
    if (array.length === 0) return 0;
    return array.reduce((a, b) => a + b, 0) / array.length;
}

function calculateStdDev(array, mean) {
    if (array.length === 0) return 0;
    const variance = array.map(x => Math.pow(x - mean, 2)).reduce((a, b) => a + b, 0) / array.length;
    return Math.sqrt(variance);
}

async function main() {
    const dataDir = process.env.TRX_BENCHMARK_DATA_DIR;
    if (!dataDir) {
        console.error("[ERROR] Environment variable TRX_BENCHMARK_DATA_DIR is not set.");
        process.exit(1);
    }

    if (!fs.existsSync(dataDir) || !fs.statSync(dataDir).isDirectory()) {
        console.error(`[ERROR] TRX_BENCHMARK_DATA_DIR directory '${dataDir}' does not exist.`);
        process.exit(1);
    }

    const resultsDir = path.join(path.dirname(__dirname), "results");
    if (!fs.existsSync(resultsDir)) {
        fs.mkdirSync(resultsDir, { recursive: true });
    }

    const tmpSaveDir = path.join(resultsDir, "tmp_benchmark_saving");
    if (!fs.existsSync(tmpSaveDir)) {
        fs.mkdirSync(tmpSaveDir, { recursive: true });
    }

    const results = {
        language: "javascript",
        data_directory: dataDir,
        results: {
            loading: {},
            saving: {}
        }
    };

    const args = process.argv.slice(2);
    const targetFilenames = args.length > 0 ? args : FILENAMES;

    for (const filename of targetFilenames) {
        const filepath = path.join(dataDir, filename);

        if (!fs.existsSync(filepath)) {
            console.error(`[ERROR] File not found: ${filepath}`);
            results.results.loading[filename] = null;
            results.results.saving[filename] = null;
            continue;
        }

        console.log(`Benchmarking ${filename}...`);

        const loadTimes = [];
        let loadingFailed = false;

        for (let i = 0; i < 11; i++) {
            evictFromCache(filepath);
            releaseMemory();

            await new Promise(resolve => setTimeout(resolve, 1000));

            const t0 = performance.now();
            try {
                const obj = await loadData(filepath);
                const duration = (performance.now() - t0) / 1000;

                const c1 = obj.offsetPt0.length;
                const c2 = obj.offsetPt0.length - 1;
                const countOk = (c1 >= MIN_EXPECTED_STREAMLINES && c1 <= MAX_EXPECTED_STREAMLINES) ||
                                (c2 >= MIN_EXPECTED_STREAMLINES && c2 <= MAX_EXPECTED_STREAMLINES);
                const pointCount = obj.pts.length / 3;

                if (!countOk || pointCount !== EXPECTED_POINTS) {
                    throw new Error(
                        `Integrity check failed: expected streamlines in range ` +
                        `[${MIN_EXPECTED_STREAMLINES}, ${MAX_EXPECTED_STREAMLINES}] and ${EXPECTED_POINTS} points, ` +
                        `got offsetPt0.length = ${c1} (streamlines could be ${c1} or ${c2}) and ${pointCount} points`
                    );
                }

                if (i === 0) {
                    console.log(`  Load Cold Run: ${duration.toFixed(4)}s`);
                } else {
                    loadTimes.push(duration);
                    console.log(`  Load Warm Run ${i}: ${duration.toFixed(4)}s`);
                }
            } catch (e) {
                console.error(`[ERROR] Loading failed for ${filename} at iteration ${i}: ${e.message}`);
                loadingFailed = true;
                break;
            }
        }

        releaseMemory();

        if (loadingFailed) {
            results.results.loading[filename] = null;
            results.results.saving[filename] = null;
            continue;
        }

        results.results.loading[filename] = loadTimes;
        const avgLoad = calculateMean(loadTimes);
        const stdLoad = calculateStdDev(loadTimes, avgLoad);
        console.log(`  Summary Load: ${avgLoad.toFixed(4)} +/- ${stdLoad.toFixed(4)} seconds`);

        // --- Benchmarking Saving ---
        const saveTimes = [];
        let savingFailed = false;

        let obj = null;
        try {
            obj = await loadData(filepath);
        } catch (e) {
            console.error(`[ERROR] Saving benchmark loader failed: ${e.message}`);
            savingFailed = true;
        }

        const ext = path.extname(filename).toLowerCase();

        if (!savingFailed) {
            console.log(`  Benchmarking Saving (11 iterations)...`);
            for (let i = 0; i < 11; i++) {
                releaseMemory();
                await new Promise(resolve => setTimeout(resolve, 1000));

                const savePath = path.join(tmpSaveDir, `tmp_save_${i}${ext}`);
                const t0 = performance.now();
                try {
                    if (ext === '.trx') {
                        saveTRX(savePath, obj, filename);
                    } else if (ext === '.trk') {
                        saveTRK(savePath, obj, filename);
                    } else if (ext === '.tck') {
                        saveTCK(savePath, obj);
                    } else if (ext === '.vtk') {
                        saveVTK(savePath, obj);
                    }
                    const duration = (performance.now() - t0) / 1000;

                    if (i === 0) {
                        console.log(`    Save Cold Run: ${duration.toFixed(4)}s`);
                    } else {
                        saveTimes.push(duration);
                        console.log(`    Save Warm Run ${i}: ${duration.toFixed(4)}s`);
                    }
                } catch (e) {
                    console.error(`  [ERROR] Saving failed at iteration ${i}: ${e.message}`);
                    savingFailed = true;
                    if (fs.existsSync(savePath)) {
                        try { fs.unlinkSync(savePath); } catch {}
                    }
                    break;
                }

                if (fs.existsSync(savePath)) {
                    try { fs.unlinkSync(savePath); } catch {}
                }
            }
        }

        releaseMemory();

        if (savingFailed) {
            results.results.saving[filename] = null;
        } else {
            results.results.saving[filename] = saveTimes;
            const avgSave = calculateMean(saveTimes);
            const stdSave = calculateStdDev(saveTimes, avgSave);
            console.log(`  Summary Save: ${avgSave.toFixed(4)} +/- ${stdSave.toFixed(4)} seconds\n`);
        }
    }

    try {
        if (fs.existsSync(tmpSaveDir)) {
            fs.rmSync(tmpSaveDir, { recursive: true, force: true });
        }
    } catch {}

    const outputJson = path.join(resultsDir, "js_results.json");
    fs.writeFileSync(outputJson, JSON.stringify(results, null, 4));
    console.log(`Results saved to ${outputJson}`);
}

main().catch(err => {
    console.error("Unhandled error in benchmark:", err);
    process.exit(1);
});
