import sys
import os


class UnsupportedPlatformError(RuntimeError):
    pass


def assert_linux_x11() -> None:
    """
    Hard platform determinism gate.

    Enforced invariants:
    - Must be Linux
    - Must have X11 DISPLAY
    - No probing, no fallback, no soft detection
    - Any mismatch is terminal
    """

    # OS check (fail-closed)
    if os.name != "posix":
        sys.stderr.write("[PLATFORM ABORT] non-posix OS\n")
        sys.stderr.flush()
        raise UnsupportedPlatformError("non-posix OS")

    # Linux check
    if not sys.platform.startswith("linux"):
        sys.stderr.write("[PLATFORM ABORT] non-linux platform\n")
        sys.stderr.flush()
        raise UnsupportedPlatformError("non-linux platform")

    # X11 check (environment-only, no probing)
    display = os.environ.get("DISPLAY")
    if not isinstance(display, str) or not display:
        sys.stderr.write("[PLATFORM ABORT] X11 DISPLAY not set\n")
        sys.stderr.flush()
        raise UnsupportedPlatformError("X11 DISPLAY missing")
