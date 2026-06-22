use std::env;
use std::fs;
use std::io::Write;
use std::path::Path;


// ---------------------------------------------------------------------------
// Custom TRK writer (trx-rs intentionally refuses TRK export)
// ---------------------------------------------------------------------------



fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        eprintln!("Usage: test_rust <input_file> <output_file>");
        return;
    }
    let input_file = &args[1];
    let output_file = &args[2];
    let input_path = Path::new(input_file);
    let output_path = Path::new(output_file);

    let _in_ext = input_path.extension().and_then(|e| e.to_str()).unwrap_or("");
    let out_ext = output_path.extension().and_then(|e| e.to_str()).unwrap_or("");

    // Load: try trx-rs first, fall back to custom loader for TRK with scalars
    let tractogram = trx_rs::read_tractogram(input_path, &trx_rs::ConversionOptions::default()).unwrap();

    // Save: trx-rs refuses TRK export, so use custom writer for .trk
    if out_ext == "trk" {
        trx_rs::legacy_io::write_trk(output_path, &tractogram).expect("Failed to save TRK");
    } else {
        let options = trx_rs::ConversionOptions::default();
        trx_rs::write_tractogram(output_path, &tractogram, &options)
            .expect("Failed to save output file");
    }
}
