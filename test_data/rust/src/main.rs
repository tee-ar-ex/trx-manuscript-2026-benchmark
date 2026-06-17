use std::env;
use std::path::Path;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        return;
    }
    let input_file = &args[1];
    let output_file = &args[2];
    let tractogram = trx_rs::read_tractogram(Path::new(input_file), &trx_rs::ConversionOptions::default()).unwrap();
    let options = trx_rs::ConversionOptions::default();
    trx_rs::write_tractogram(Path::new(output_file), &tractogram, &options).unwrap();
}
