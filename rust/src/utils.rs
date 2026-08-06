use std::path::Path;

use std::process::Command;

/// Evicts a file from the OS page cache using system drop caches.
pub fn evict_from_cache<P: AsRef<Path>>(_path: P) -> std::io::Result<()> {
    let status = Command::new("sh")
        .arg("-c")
        .arg("sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null")
        .status()?;

    if !status.success() {
        return Err(std::io::Error::new(
            std::io::ErrorKind::Other,
            "Cache eviction failed",
        ));
    }

    Ok(())
}
