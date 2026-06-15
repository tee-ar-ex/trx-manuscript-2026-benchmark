use std::collections::HashMap;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::Instant;
use std::io::Write;
use serde::Serialize;

mod utils;

const FILENAMES: &[&str] = &[
    "f16_ui32_w_metadata.trx",
    "f16_ui32_wo_metadata.trx",
    "f16_ui64_w_metadata.trx",
    "f16_ui64_wo_metadata.trx",
    "f32_ui64_w_metadata.trx",
    "f32_ui64_wo_metadata.trx",
    "f64_ui32_w_metadata.trx",
    "f64_ui32_wo_metadata.trx",
    "f32_ui32_w_metadata.trx",
    "f32_ui32_wo_metadata.trx",
    "f64_ui64_w_metadata.trx",
    "f64_ui64_wo_metadata.trx",
    "f32_w_metadata.trk",
    "f32_wo_metadata.trk",
    "f32.tck",
    "f32_ui32_wo_metadata.vtk",
    "f32_ui64_wo_metadata.vtk",
    "f64_ui32_wo_metadata.vtk",
    "f64_ui64_wo_metadata.vtk",
    "f32_ui64_w_metadata.vtk",
    "f64_ui64_w_metadata.vtk",
];

static EXPECTED_STREAMLINES: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
static EXPECTED_VERTICES: std::sync::OnceLock<usize> = std::sync::OnceLock::new();

#[derive(Serialize)]
struct InnerResults {
    loading: HashMap<String, Vec<f64>>,
    saving: HashMap<String, Vec<f64>>,
}

#[derive(Serialize)]
struct BenchmarkResults {
    language: String,
    data_directory: String,
    results: InnerResults,
}

fn write_trk(path: &Path, tractogram: &trx_rs::Tractogram) -> std::result::Result<(), Box<dyn std::error::Error>> {
    let mut file = fs::File::create(path)?;
    let mut header_bytes = vec![0u8; 1000];

    // Magic: "TRACK"
    header_bytes[0..5].copy_from_slice(b"TRACK");

    // Dimensions
    let header = tractogram.header();
    let dims = [
        header.dimensions[0] as i16,
        header.dimensions[1] as i16,
        header.dimensions[2] as i16,
    ];
    header_bytes[6..8].copy_from_slice(&dims[0].to_le_bytes());
    header_bytes[8..10].copy_from_slice(&dims[1].to_le_bytes());
    header_bytes[10..12].copy_from_slice(&dims[2].to_le_bytes());

    // Compute voxel sizes from affine matrix columns norm
    let vox_to_ras = header.voxel_to_rasmm;
    let voxel_sizes = [
        ((vox_to_ras[0][0].powi(2) + vox_to_ras[1][0].powi(2) + vox_to_ras[2][0].powi(2)).sqrt()) as f32,
        ((vox_to_ras[0][1].powi(2) + vox_to_ras[1][1].powi(2) + vox_to_ras[2][1].powi(2)).sqrt()) as f32,
        ((vox_to_ras[0][2].powi(2) + vox_to_ras[1][2].powi(2) + vox_to_ras[2][2].powi(2)).sqrt()) as f32,
    ];
    header_bytes[12..16].copy_from_slice(&voxel_sizes[0].to_le_bytes());
    header_bytes[16..20].copy_from_slice(&voxel_sizes[1].to_le_bytes());
    header_bytes[20..24].copy_from_slice(&voxel_sizes[2].to_le_bytes());

    // vox_to_ras
    let mut offset = 440;
    for r in 0..4 {
        for c in 0..4 {
            let val = vox_to_ras[r][c] as f32;
            header_bytes[offset..offset+4].copy_from_slice(&val.to_le_bytes());
            offset += 4;
        }
    }

    // Voxel order
    header_bytes[948..952].copy_from_slice(b"RAS\0");

    // Number of tracks
    let nb_streamlines = tractogram.nb_streamlines() as i32;
    header_bytes[988..992].copy_from_slice(&nb_streamlines.to_le_bytes());

    // Version
    let version = 2i32;
    header_bytes[992..996].copy_from_slice(&version.to_le_bytes());

    // Header size
    let hdr_size = 1000i32;
    header_bytes[996..1000].copy_from_slice(&hdr_size.to_le_bytes());

    file.write_all(&header_bytes)?;

    // Streamlines payload
    let offsets = tractogram.offsets();
    let positions = tractogram.positions();
    let mut chunk = Vec::with_capacity(4 * 1024 * 1024);

    for i in 0..tractogram.nb_streamlines() {
        let start = offsets[i] as usize;
        let end = offsets[i+1] as usize;
        let n_points = (end - start) as i32;

        chunk.extend_from_slice(&n_points.to_le_bytes());
        for j in start..end {
            let pt = positions[j];
            chunk.extend_from_slice(&pt[0].to_le_bytes());
            chunk.extend_from_slice(&pt[1].to_le_bytes());
            chunk.extend_from_slice(&pt[2].to_le_bytes());
        }

        if chunk.len() >= 4000000 {
            file.write_all(&chunk)?;
            chunk.clear();
        }
    }

    if !chunk.is_empty() {
        file.write_all(&chunk)?;
    }

    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 1. Locate dataset directory
    let data_dir_str = match env::var("TRX_BENCHMARK_DATA_DIR") {
        Ok(val) => val,
        Err(_) => {
            eprintln!("Error: TRX_BENCHMARK_DATA_DIR environment variable is not set.");
            std::process::exit(1);
        }
    };
    let data_dir = Path::new(&data_dir_str);
    if !data_dir.exists() {
        eprintln!("Error: TRX_BENCHMARK_DATA_DIR does not point to an existing directory: {:?}", data_dir);
        std::process::exit(1);
    }

    let mut loading = HashMap::new();
    let mut saving = HashMap::new();

    // Create a local tmp directory for saving benchmark
    let tmp_dir = PathBuf::from("tmp_benchmark_saving");
    if !tmp_dir.exists() {
        fs::create_dir_all(&tmp_dir)?;
    }

    // Iterate through all target files
    for filename in FILENAMES {
        let path = data_dir.join(filename);
        if !path.exists() {
            println!("[FAIL] {} not found.", path.display());
            continue;
        }

        let ext = if filename.ends_with(".trx") {
            ".trx"
        } else if filename.ends_with(".tck") {
            ".tck"
        } else if filename.ends_with(".vtk") {
            ".vtk"
        } else if filename.ends_with(".trk") {
            ".trk"
        } else {
            ""
        };

        // --- Benchmarking Loading ---
        println!("Benchmarking Loading for {} (11 iterations)...", filename);
        let mut load_times = Vec::new();
        for i in 0..11 {
            // Evict file from cache
            if let Err(e) = utils::evict_from_cache(&path) {
                println!("      [WARN] Cache eviction failed for {}: {}", filename, e);
            }
            std::thread::sleep(std::time::Duration::from_secs(1));

            let t0 = Instant::now();
            let tractogram = match ext {
                ".trk" => utils::load_trk(&path).map_err(|e| e.to_string()),
                ".vtk" => utils::load_vtk(&path).map_err(|e| e.to_string()),
                _ => trx_rs::read_tractogram(&path, &trx_rs::ConversionOptions::default()).map_err(|e| e.to_string())
            };
            let tractogram = match tractogram {
                Ok(t) => t,
                Err(e) => {
                    println!("    {:2} - [ERROR] Loading failed: {}", i, e);
                    continue;
                }
            };
            let duration = t0.elapsed().as_secs_f64();

            let nb_streamlines = tractogram.nb_streamlines();
            let nb_vertices = tractogram.nb_vertices();
            
            let expected_s = *EXPECTED_STREAMLINES.get_or_init(|| nb_streamlines);
            let expected_v = *EXPECTED_VERTICES.get_or_init(|| nb_vertices);
            
            if nb_streamlines != expected_s || nb_vertices != expected_v {
                println!(
                    "    [FAIL] {} - Wrong size detected! streamlines: {}, vertices: {}",
                    filename, nb_streamlines, nb_vertices
                );
            }

            if i == 0 {
                println!("    [COLD RUN] {:.4}s (Initialization overhead)", duration);
            } else {
                load_times.push(duration);
                println!("    {:2} - {:.4}s", i - 1, duration);
            }
        }

        if !load_times.is_empty() {
            let avg = mean(&load_times);
            let std_dev = stddev(&load_times, avg);
            println!("Summary for {}: {:.4} +/- {:.4} seconds.\n", filename, avg, std_dev);
            loading.insert(filename.to_string(), load_times);
        }

        // Load the tractogram once for saving benchmark
        let tractogram = match ext {
            ".trk" => utils::load_trk(&path).map_err(|e| e.to_string()),
            ".vtk" => utils::load_vtk(&path).map_err(|e| e.to_string()),
            _ => trx_rs::read_tractogram(&path, &trx_rs::ConversionOptions::default()).map_err(|e| e.to_string())
        };
        let tractogram = match tractogram {
            Ok(t) => t,
            Err(e) => {
                println!("[ERROR] Saving benchmark loader failed: {}", e);
                continue;
            }
        };

        // Determine precision
        let dtype = if filename.contains("f16") {
            trx_rs::DType::Float16
        } else if filename.contains("f64") {
            trx_rs::DType::Float64
        } else {
            trx_rs::DType::Float32
        };

        let options = trx_rs::ConversionOptions {
            trx_positions_dtype: dtype,
            ..Default::default()
        };



        println!("Benchmarking Saving for {} (11 iterations)...", filename);
        let mut save_times = Vec::new();
        for i in 0..11 {
            std::thread::sleep(std::time::Duration::from_secs(1));

            let save_path = tmp_dir.join(format!("tmp_save_{}{}", i, ext));

            let t0 = Instant::now();
            let write_res = if ext == ".trk" {
                write_trk(&save_path, &tractogram)
            } else {
                trx_rs::write_tractogram(&save_path, &tractogram, &options).map_err(|e| e.into())
            };
            let duration = t0.elapsed().as_secs_f64();

            if let Err(e) = write_res {
                println!("    {:2} - [ERROR] Saving failed: {}", i, e);
            }

            if i == 0 {
                println!("    [COLD RUN] {:.4}s (Initialization overhead)", duration);
            } else {
                save_times.push(duration);
                println!("    {:2} - {:.4}s", i - 1, duration);
            }

            // Cleanup save file
            if save_path.exists() {
                if save_path.is_dir() {
                    let _ = fs::remove_dir_all(&save_path);
                } else {
                    let _ = fs::remove_file(&save_path);
                }
            }
        }

        if !save_times.is_empty() {
            let avg = mean(&save_times);
            let std_dev = stddev(&save_times, avg);
            println!("Summary for {}: {:.4} +/- {:.4} seconds.\n", filename, avg, std_dev);
            saving.insert(filename.to_string(), save_times);
        }
    }

    // Final clean up of saving temp directory
    if tmp_dir.exists() {
        let _ = fs::remove_dir_all(&tmp_dir);
    }

    // 6. Serialize results to results/rust_results.json
    let results_dir = std::env::current_dir()?.join("results");
    if !results_dir.exists() {
        fs::create_dir_all(&results_dir)?;
    }

    let results = BenchmarkResults {
        language: "rust".to_string(),
        data_directory: data_dir_str,
        results: InnerResults { loading, saving },
    };

    let output_json = results_dir.join("rust_results.json");
    let file = fs::File::create(&output_json)?;
    serde_json::to_writer_pretty(file, &results)?;
    println!("Results saved to {}", output_json.display());

    Ok(())
}

fn mean(data: &[f64]) -> f64 {
    let sum: f64 = data.iter().sum();
    sum / data.len() as f64
}

fn stddev(data: &[f64], mean: f64) -> f64 {
    let variance = data.iter()
        .map(|value| {
            let diff = mean - value;
            diff * diff
        })
        .sum::<f64>() / data.len() as f64;
    variance.sqrt()
}
