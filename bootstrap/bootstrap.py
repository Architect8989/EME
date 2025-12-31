import os
import sys
import signal

from core.os_detection import detect_os
from body.linux_backend import LinuxBackend
from core.safety_guard import SafetyGuard

MODE = "OBSERVE_ONLY"   # newborn lock, do not change

def hard_abort(reason: str):
    print(f"[BOOTSTRAP ABORT] {reason}", file=sys.stderr)
    sys.exit(1)

def bootstrap():
    # 1. OS detection
    facts = detect_os()

    # 2. Enforce X11
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type != "x11":
        hard_abort("Wayland detected. X11 required.")

    display = os.environ.get("DISPLAY")
    if not display:
        hard_abort("DISPLAY not set. Cannot attach to X11 session.")

    # 3. Initialize backend
    backend = LinuxBackend()

    # 4. Backend self-test (MANDATORY)
    try:
        backend.self_test()
    except Exception as e:
        hard_abort(f"Backend self-test failed: {e}")

    # 5. Safety guard (authoritative)
    guard = SafetyGuard()
    guard.lock_observe_only()

    # 6. Kill switch (SIGINT / SIGTERM)
    def _kill(_sig, _frame):
        guard.emergency_stop("Manual kill signal received")
        sys.exit(0)

    signal.signal(signal.SIGINT, _kill)
    signal.signal(signal.SIGTERM, _kill)

    return {
        "facts": facts,
        "mode": MODE,
        "display": display,
        "backend": "READY",
        "guard": "ARMED"
    }

if __name__ == "__main__":
    print(bootstrap())
