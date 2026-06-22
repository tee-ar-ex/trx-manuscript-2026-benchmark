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

