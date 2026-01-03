from typing import Dict


class UnsupportedPlatformError(RuntimeError):
    pass


def detect_os() -> Dict[str, str]:
    """
    Deterministic placeholder.
    Platform detection is not permitted in a frozen artifact.
    """
    raise UnsupportedPlatformError(
        "Platform detection is forbidden in this build"
    )
