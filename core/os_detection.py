import platform
import json
from typing import Dict


def detect_os() -> Dict[str, str]:
    """
    Authoritative OS fingerprint.
    No guessing. No heuristics.
    Called once at startup.
    """

    facts = {
        "family": platform.system().lower(),      # linux / windows / darwin
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
    }

    return facts


if __name__ == "__main__":
    print(json.dumps(detect_os(), indent=2))
