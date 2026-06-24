use std::env;

use std::path::Path;


// ---------------------------------------------------------------------------
// Custom TRK writer (trx-rs intentionally refuses TRK export)
// ---------------------------------------------------------------------------



fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        eprintln!("Usage: test_rust <input_file> <output_file> [--ref <nifti>]");
        return;
    }
    let input_file = &args[1];
    let output_file = &args[2];
    let input_path = Path::new(input_file);
    let output_path = Path::new(output_file);

    let mut ref_nifti: Option<&Path> = None;
    if args.len() >= 5 && args[3] == "--ref" {
        ref_nifti = Some(Path::new(&args[4]));
    }

    let _in_ext = input_path.extension().and_then(|e| e.to_str()).unwrap_or("");
    let out_ext = output_path.extension().and_then(|e| e.to_str()).unwrap_or("");

    let mut tractogram = trx_rs::read_tractogram(input_path, &trx_rs::ConversionOptions::default()).unwrap();
    if let Some(ref_path) = ref_nifti {
        if let Ok(hdr) = trx_rs::legacy_io::load_nifti_header(ref_path) {
            tractogram.set_header(hdr);
        }
    }

    if out_ext == "trk" {
        trx_rs::legacy_io::write_trk(output_path, &tractogram, ref_nifti).expect("Failed to save TRK");
    } else {
        let options = trx_rs::ConversionOptions::default();
        trx_rs::write_tractogram(output_path, &tractogram, &options)
            .expect("Failed to save output file");
    }
}
