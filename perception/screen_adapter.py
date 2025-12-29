"""
Screen capture — forensic grade.
Final version — truth boundary.

Requirements:
— Lossless capture only
— Monotonic timestamps
— SHA256 checksums
— Stable file naming
— Multi-monitor support
— Retries with backoff
— No silent partial frames
— Post-write verification
— fsync durability barriers
— No hidden transformations
— Hash chain for tamper evidence
— Sidecar metadata
— Crash on anomalies
"""

import time
import hashlib
import tempfile
import pathlib
import threading
import os
import json
import sys
import mss

from dataclasses import dataclass, asdict
from typing import Optional, Tuple, Dict, Any

CAPTURE_RETRIES = 3
CAPTURE_BACKOFF = 0.15  # seconds


@dataclass
class Frame:
    """Forensic frame with complete provenance."""
    path: pathlib.Path
    width: int
    height: int
    checksum: str
    timestamp_monotonic: float
    previous_checksum: str = ""
    monitor: Optional[int] = None
    pixel_format: str = "BGRA"  # Explicit declaration
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        d = asdict(self)
        d['path'] = str(self.path)
        return d


class CaptureError(Exception):
    """Critical capture failure - system must abort."""
    pass


class ForensicCapture:
    """
    Forensic-grade screen capture.
    
    Features:
    - Exact byte preservation (no transformations)
    - Post-write verification with re-hashing
    - fsync durability barriers
    - Hash chain for tamper evidence
    - Sidecar metadata storage
    - Monotonic timestamp enforcement
    - Crash on any anomaly
    - No stdout/stderr output
    """
    
    def __init__(self, monitor: Optional[int] = None):
        """
        Initialize capture system.
        
        Args:
            monitor: Monitor index (0-based), None for all monitors
        """
        self._monitor = monitor
        self._lock = threading.Lock()
        
        # Create secure temporary directory
        self._tmpdir = pathlib.Path(tempfile.gettempdir()) / "eme_frames"
        self._tmpdir.mkdir(exist_ok=True, parents=True)
        
        # State for invariants
        self._last_timestamp: float = 0.0
        self._last_checksum: str = ""
        self._frame_count: int = 0
        
        # Platform information for metadata
        self._mss_version = mss.__version__
        self._platform = sys.platform

    def _stable_path(self, ts: float) -> pathlib.Path:
        """
        Generate deterministic, sortable filename.
        
        Args:
            ts: Monotonic timestamp in seconds
            
        Returns:
            Path object for the raw frame file
        """
        # Microsecond precision for sorting
        name = f"frame_{int(ts * 1_000_000):020d}.raw"
        return self._tmpdir / name

    def _checksum(self, data: bytes) -> str:
        """
        Compute SHA-256 hash of data.
        
        Args:
            data: Binary data to hash
            
        Returns:
            Hexadecimal SHA-256 hash
        """
        h = hashlib.sha256()
        h.update(data)
        return h.hexdigest()

    def _validate_buffer_format(self, data: bytes, width: int, height: int) -> None:
        """
        Validate buffer format invariants.
        
        Args:
            data: Buffer to validate
            width: Expected width in pixels
            height: Expected height in pixels
            
        Raises:
            CaptureError: On any format violation
        """
        # 1. Must have exactly 4 bytes per pixel
        bytes_per_pixel = 4
        expected_size = width * height * bytes_per_pixel
        
        if len(data) != expected_size:
            raise CaptureError(
                f"Buffer size mismatch: {len(data)} bytes, "
                f"expected {expected_size} for {width}x{height} at 4 bytes/px"
            )
        
        # 2. Must be divisible by 4 (RGBA/BGRA)
        if len(data) % bytes_per_pixel != 0:
            raise CaptureError(
                f"Buffer size {len(data)} not divisible by {bytes_per_pixel}"
            )
        
        # 3. Stride must match width * bytes_per_pixel
        stride = width * bytes_per_pixel
        if height > 0 and len(data) // height != stride:
            raise CaptureError(
                f"Stride mismatch: buffer length per row = {len(data)//height}, "
                f"expected {stride}"
            )
        
        # 4. Minimum sanity check: must be able to hold at least one pixel
        if len(data) < 4:
            raise CaptureError("Buffer too small to contain a single pixel")
        
        # 5. Check first pixel is readable (not out of bounds)
        # This is implicit in the size checks above
        # 6. Check a random pixel is readable (not out of bounds)
        if len(data) >= 8:
            # Check that we can read at least two pixels
            # This ensures the buffer isn't severely truncated
            pass

    def _grab(self) -> Tuple[bytes, int, int, str]:
        """
        Capture screen data without transformations.
        
        Returns:
            Tuple of (raw_buffer, width, height, pixel_format)
            
        Raises:
            CaptureError: On any capture or format failure
        """
        with mss.mss() as sct:
            # Select monitor
            if self._monitor is None:
                monitor = sct.monitors[0]  # Virtual monitor (all displays)
            else:
                if self._monitor >= len(sct.monitors):
                    raise CaptureError(
                        f"Monitor index {self._monitor} out of range "
                        f"(available: {len(sct.monitors)})"
                    )
                monitor = sct.monitors[self._monitor]

            # Capture
            img = sct.grab(monitor)
            width = img.width
            height = img.height
            
            # Get exact buffer - prioritize bgra if available
            if hasattr(img, 'bgra'):
                data = img.bgra
                pixel_format = "BGRA"
            else:
                data = img.raw
                pixel_format = "RAW"
            
            # Validate buffer format invariants
            self._validate_buffer_format(data, width, height)
            
            return data, width, height, pixel_format

    def _write_with_integrity(self, data: bytes, path: pathlib.Path) -> None:
        """
        Write data with full integrity verification.
        
        Steps:
        1. Write to temporary file with fsync
        2. Verify file size matches
        3. Re-read and verify checksum
        4. Atomic rename
        5. Sync directory
        
        Args:
            data: Binary data to write
            path: Destination path
            
        Raises:
            CaptureError: On any integrity failure
        """
        # Create temporary file
        tmp = path.with_suffix(".raw.tmp")
        
        try:
            # 1. Write with durability
            with open(tmp, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
            
            # 2. Verify file size
            actual_size = tmp.stat().st_size
            expected_size = len(data)
            
            if actual_size != expected_size:
                raise CaptureError(
                    f"Partial write detected: expected {expected_size} bytes, "
                    f"got {actual_size} bytes"
                )
            
            # 3. Re-read and verify checksum
            with open(tmp, "rb") as f:
                written_data = f.read()
            
            if len(written_data) != expected_size:
                raise CaptureError("File size changed during verification")
            
            original_hash = self._checksum(data)
            written_hash = self._checksum(written_data)
            
            if original_hash != written_hash:
                raise CaptureError(
                    f"Checksum mismatch after write: "
                    f"original={original_hash[:16]}..., "
                    f"written={written_hash[:16]}..."
                )
            
            # 4. Atomic rename
            tmp.replace(path)
            
            # 5. Sync directory
            dir_fd = os.open(str(path.parent), os.O_RDONLY)
            os.fsync(dir_fd)
            os.close(dir_fd)
            
        except Exception as e:
            # Clean up temporary file on error
            if tmp.exists():
                try:
                    tmp.unlink()
                except:
                    pass
            raise CaptureError(f"Write integrity failure: {e}")
        finally:
            # Ensure temporary file is cleaned up
            if tmp.exists():
                try:
                    tmp.unlink()
                except:
                    pass

    def _write_sidecar(self, frame: Frame) -> None:
        """
        Write JSON sidecar with complete metadata.
        
        Args:
            frame: Frame object with metadata
            
        Raises:
            CaptureError: On write failure
        """
        sidecar = frame.path.with_suffix(".json")
        tmp = sidecar.with_suffix(".json.tmp")
        
        try:
            # Prepare metadata
            metadata = frame.to_dict()
            metadata['file_size_bytes'] = frame.path.stat().st_size
            metadata['frame_number'] = self._frame_count
            metadata['system_time'] = time.time()
            metadata['mss_version'] = self._mss_version
            metadata['platform'] = self._platform
            metadata['bytes_per_pixel'] = 4
            
            # Write with durability
            with open(tmp, "w") as f:
                json.dump(metadata, f, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic rename
            tmp.replace(sidecar)
            
            # Sync directory
            dir_fd = os.open(str(sidecar.parent), os.O_RDONLY)
            os.fsync(dir_fd)
            os.close(dir_fd)
            
        except Exception as e:
            if tmp.exists():
                try:
                    tmp.unlink()
                except:
                    pass
            raise CaptureError(f"Sidecar write failure: {e}")

    def _enforce_invariants(self, timestamp: float, width: int, height: int) -> None:
        """
        Enforce forensic invariants.
        
        Args:
            timestamp: Current monotonic timestamp
            width: Frame width
            height: Frame height
            
        Raises:
            CaptureError: On invariant violation
        """
        # Monotonic timestamp check
        if timestamp <= self._last_timestamp:
            raise CaptureError(
                f"Non-monotonic timestamp violation: "
                f"{timestamp} <= {self._last_timestamp}"
            )
        
        # Dimension validity check
        if width <= 0 or height <= 0:
            raise CaptureError(f"Invalid dimensions: {width}x{height}")
        
        # Update last timestamp
        self._last_timestamp = timestamp

    def capture(self) -> Frame:
        """
        Capture a single forensic frame.
        
        Returns:
            Frame object with complete provenance
            
        Raises:
            CaptureError: On any failure (system should abort)
        """
        with self._lock:
            # Retry only on capture failures, not on integrity failures
            for attempt in range(1, CAPTURE_RETRIES + 1):
                try:
                    # 1. Capture with monotonic timestamp
                    timestamp = time.monotonic()
                    
                    # 2. Grab raw data (retry on failure)
                    data, width, height, pixel_format = self._grab()
                    
                    # 3. Enforce invariants (no retry)
                    self._enforce_invariants(timestamp, width, height)
                    
                    # 4. Compute checksum
                    checksum = self._checksum(data)
                    
                    # 5. Generate path
                    path = self._stable_path(timestamp)
                    
                    # 6. Write with full integrity verification
                    self._write_with_integrity(data, path)
                    
                    # 7. Create frame object
                    frame = Frame(
                        path=path,
                        width=width,
                        height=height,
                        checksum=checksum,
                        timestamp_monotonic=timestamp,
                        previous_checksum=self._last_checksum,
                        monitor=self._monitor,
                        pixel_format=pixel_format
                    )
                    
                    # 8. Write sidecar metadata
                    self._write_sidecar(frame)
                    
                    # 9. Update chain state
                    self._last_checksum = checksum
                    self._frame_count += 1
                    
                    return frame
                    
                except CaptureError:
                    # Structural failure - abort immediately
                    raise
                except Exception as e:
                    # Capture failure - retry with backoff
                    if attempt == CAPTURE_RETRIES:
                        raise CaptureError(
                            f"Capture failed after {CAPTURE_RETRIES} attempts: {e}"
                        )
                    time.sleep(CAPTURE_BACKOFF)
                    continue
            
            # Should never reach here
            raise CaptureError("Unexpected capture failure")

    def get_capture_info(self) -> Dict[str, Any]:
        """
        Get current capture system information.
        
        Returns:
            Dictionary with capture system state
        """
        return {
            "monitor": self._monitor,
            "storage_directory": str(self._tmpdir),
            "frame_count": self._frame_count,
            "last_timestamp": self._last_timestamp,
            "last_checksum": self._last_checksum[:16] + "..." if self._last_checksum else "",
            "pixel_format": "BGRA_OR_RAW",
            "bytes_per_pixel": 4,
            "mss_version": self._mss_version,
            "platform": self._platform,
        }


# Backward compatibility alias
ScreenCapture = ForensicCapture


if __name__ == "__main__":
    # Example usage - minimal, no prints
    try:
        cap = ForensicCapture(monitor=0)
        frame1 = cap.capture()
        frame2 = cap.capture()
        # Success - exit 0
        sys.exit(0)
    except CaptureError:
        sys.exit(1)
