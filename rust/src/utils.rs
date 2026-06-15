use std::fs::File;
use std::os::unix::io::AsRawFd;
use std::path::Path;

/// Evicts a file from the OS page cache using posix_fadvise.
pub fn evict_from_cache<P: AsRef<Path>>(path: P) -> std::io::Result<()> {
    let file = File::open(path)?;
    let fd = file.as_raw_fd();
    let len = file.metadata()?.len();

    let ret = unsafe {
        libc::posix_fadvise(fd, 0, len as libc::off_t, libc::POSIX_FADV_DONTNEED)
    };

    if ret != 0 {
        return Err(std::io::Error::from_raw_os_error(ret));
    }

    Ok(())
}

pub fn load_trk(path: &Path) -> Result<trx_rs::Tractogram, Box<dyn std::error::Error>> {
    use std::io::Read;
    let mut f = File::open(path)?;
    let mut buffer = Vec::new();
    f.read_to_end(&mut buffer)?;

    if buffer.len() < 1000 {
        return Err("File too small".into());
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

pub fn load_vtk(path: &Path) -> Result<trx_rs::Tractogram, Box<dyn std::error::Error>> {
    use std::io::Read;
    let mut f = File::open(path)?;
    let mut buffer = Vec::new();
    f.read_to_end(&mut buffer)?;

    let header_str = String::from_utf8_lossy(&buffer[0..std::cmp::min(1024, buffer.len())]);
    let points_idx = header_str.find("POINTS ").ok_or("No POINTS")?;
    
    let points_str = header_str[points_idx..].split_whitespace().nth(1).ok_or("No POINTS count")?;
    let num_points: usize = points_str.parse()?;

    let mut is_double = false;
    if let Some(type_str) = header_str[points_idx..].split_whitespace().nth(2) {
        if type_str == "double" {
            is_double = true;
        }
    }

    let header_end = header_str[points_idx..].find('\n').unwrap() + points_idx + 1;
    let mut pts = Vec::with_capacity(num_points * 3);
    
    let mut offset = header_end;
    for _ in 0..num_points * 3 {
        if is_double {
            let val = f64::from_be_bytes(buffer[offset..offset+8].try_into().unwrap());
            pts.push(val as f32);
            offset += 8;
        } else {
            let val = f32::from_be_bytes(buffer[offset..offset+4].try_into().unwrap());
            pts.push(val);
            offset += 4;
        }
    }

    // Since PTS is binary, the "LINES " text appears right after the pts binary block.
    // So the offset is exactly where "LINES " starts.
    // However, to be safe, we can just search from offset.
    let search_window = std::cmp::min(offset + 1024, buffer.len());
    let lines_str_chunk = String::from_utf8_lossy(&buffer[offset..search_window]);
    
    let lines_idx_in_chunk = lines_str_chunk.find("LINES ").ok_or("No LINES")?;
    let lines_idx = offset + lines_idx_in_chunk;
    
    let lines_str = lines_str_chunk[lines_idx_in_chunk..].split_whitespace().nth(1).ok_or("No LINES count")?;
    let num_lines: usize = lines_str.parse()?;

    let lines_header_end = lines_str_chunk[lines_idx_in_chunk..].find('\n').unwrap() + lines_idx + 1;
    offset = lines_header_end;

    let mut tr = trx_rs::Tractogram::new();
    
    if buffer[offset..].starts_with(b"OFFSETS") {
        let offsets_header_end = buffer[offset..].iter().position(|&c| c == b'\n').unwrap() + offset + 1;
        let is_int64 = buffer[offset..offsets_header_end].windows(5).any(|w| w == b"int64");
        offset = offsets_header_end;
        
        let mut offsets_vec = Vec::with_capacity(num_lines);
        for _ in 0..num_lines {
            if is_int64 {
                let val = u64::from_be_bytes(buffer[offset..offset+8].try_into().unwrap());
                offsets_vec.push(val as usize);
                offset += 8;
            } else {
                let val = u32::from_be_bytes(buffer[offset..offset+4].try_into().unwrap());
                offsets_vec.push(val as usize);
                offset += 4;
            }
        }
        
        for i in 0..num_lines-1 {
            let start = offsets_vec[i];
            let end = offsets_vec[i+1];
            let mut streamline = Vec::with_capacity(end - start);
            for pt_idx in start..end {
                streamline.push([pts[pt_idx*3], pts[pt_idx*3+1], pts[pt_idx*3+2]]);
            }
            tr.push_streamline(&streamline)?;
        }
        return Ok(tr);
    }

    let mut pt_idx = 0;
    for _ in 0..num_lines {
        if offset + 4 > buffer.len() { break; }
        let n_pts = i32::from_be_bytes(buffer[offset..offset+4].try_into().unwrap());
        offset += 4;
        
        if n_pts <= 0 { continue; }
        if pt_idx + (n_pts as usize) > num_points { break; }
        
        let mut streamline = Vec::with_capacity(n_pts as usize);
        for _ in 0..n_pts {
            offset += 4;
            streamline.push([pts[pt_idx*3], pts[pt_idx*3+1], pts[pt_idx*3+2]]);
            pt_idx += 1;
        }
        tr.push_streamline(&streamline)?;
    }

    Ok(tr)
}
