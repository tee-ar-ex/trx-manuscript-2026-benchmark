use std::env;
use std::fs;
use std::io::{Read, Write};
use std::path::Path;

// ---------------------------------------------------------------------------
// Custom TRK loader (trx-rs refuses files with scalars/properties)
// ---------------------------------------------------------------------------

fn load_trk(path: &Path) -> Result<trx_rs::Tractogram, Box<dyn std::error::Error>> {
    let mut f = fs::File::open(path)?;
    let mut buffer = Vec::new();
    f.read_to_end(&mut buffer)?;

    if buffer.len() < 1000 {
        return Err("File too small for TRK".into());
    }

    let n_scalars = i16::from_le_bytes(buffer[36..38].try_into().unwrap());
    let n_properties = i16::from_le_bytes(buffer[238..240].try_into().unwrap());

    let mut tr = trx_rs::Tractogram::new();
    let mut offset = 1000;

    while offset + 4 <= buffer.len() {
        let n_points = i32::from_le_bytes(buffer[offset..offset+4].try_into().unwrap());
        offset += 4;

        let mut streamline = Vec::with_capacity(n_points as usize);
        for _ in 0..n_points {
            let x = f32::from_le_bytes(buffer[offset..offset+4].try_into().unwrap());
            let y = f32::from_le_bytes(buffer[offset+4..offset+8].try_into().unwrap());
            let z = f32::from_le_bytes(buffer[offset+8..offset+12].try_into().unwrap());
            streamline.push([x, y, z]);
            offset += (3 + n_scalars as usize) * 4;
        }
        tr.push_streamline(&streamline)?;
        offset += (n_properties as usize) * 4;
    }

    Ok(tr)
}

// ---------------------------------------------------------------------------
// Custom TRK writer (trx-rs intentionally refuses TRK export)
// ---------------------------------------------------------------------------

fn write_trk(path: &Path, tractogram: &trx_rs::Tractogram) -> Result<(), Box<dyn std::error::Error>> {
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

    // Compute voxel sizes from affine
    let vox_to_ras = header.voxel_to_rasmm;
    let voxel_sizes = [
        ((vox_to_ras[0][0].powi(2) + vox_to_ras[1][0].powi(2) + vox_to_ras[2][0].powi(2)).sqrt()) as f32,
        ((vox_to_ras[0][1].powi(2) + vox_to_ras[1][1].powi(2) + vox_to_ras[2][1].powi(2)).sqrt()) as f32,
        ((vox_to_ras[0][2].powi(2) + vox_to_ras[1][2].powi(2) + vox_to_ras[2][2].powi(2)).sqrt()) as f32,
    ];
    header_bytes[12..16].copy_from_slice(&voxel_sizes[0].to_le_bytes());
    header_bytes[16..20].copy_from_slice(&voxel_sizes[1].to_le_bytes());
    header_bytes[20..24].copy_from_slice(&voxel_sizes[2].to_le_bytes());

    // vox_to_ras 4x4 matrix at offset 440
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

    // Number of streamlines
    let nb_streamlines = tractogram.nb_streamlines() as i32;
    header_bytes[988..992].copy_from_slice(&nb_streamlines.to_le_bytes());

    // Version
    header_bytes[992..996].copy_from_slice(&2i32.to_le_bytes());

    // Header size
    header_bytes[996..1000].copy_from_slice(&1000i32.to_le_bytes());

    file.write_all(&header_bytes)?;

    // Streamline payload
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

        if chunk.len() >= 4_000_000 {
            file.write_all(&chunk)?;
            chunk.clear();
        }
    }

    if !chunk.is_empty() {
        file.write_all(&chunk)?;
    }

    Ok(())
}

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

    let in_ext = input_path.extension().and_then(|e| e.to_str()).unwrap_or("");
    let out_ext = output_path.extension().and_then(|e| e.to_str()).unwrap_or("");

    // Load: try trx-rs first, fall back to custom loader for TRK with scalars
    let tractogram = match trx_rs::read_tractogram(input_path, &trx_rs::ConversionOptions::default()) {
        Ok(t) => t,
        Err(e) => {
            if in_ext == "trk" {
                eprintln!("trx-rs refused TRK ({}), using custom loader", e);
                load_trk(input_path).expect("Custom TRK loader also failed")
            } else {
                panic!("Failed to load input file: {}", e);
            }
        }
    };

    // Save: trx-rs refuses TRK export, so use custom writer for .trk
    if out_ext == "trk" {
        write_trk(output_path, &tractogram).expect("Failed to save TRK");
    } else {
        let options = trx_rs::ConversionOptions::default();
        trx_rs::write_tractogram(output_path, &tractogram, &options)
            .expect("Failed to save output file");
    }
}
