import os
import sys
import signal

from core.mode_gate import ModeGate, Mode
from core.environment_contract import EnvironmentContract
from core.poison import Poison
from core.system_state import SystemState


def hard_abort(reason: str):
    sys.stderr.write(f"[BOOTSTRAP ABORT] {reason}\n")
    sys.stderr.flush()
    sys.exit(1)


def bootstrap():
    Poison.assert_clean()
    ModeGate.disarm()

    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type != "x11":
        hard_abort("Wayland detected. X11 required.")

    display = os.environ.get("DISPLAY")
    if not display:
        hard_abort("DISPLAY not set.")

    try:
        env_fp = EnvironmentContract.verify()
    except Exception as e:
        hard_abort(str(e))

    def _kill(_sig, _frame):
        try:
            ModeGate.kill("Manual kill signal received")
        except Exception:
            pass
        sys.exit(1)

    signal.signal(signal.SIGINT, _kill)
    signal.signal(signal.SIGTERM, _kill)

    ModeGate.arm(Mode.PROBE)

    SystemState.mark_initialized()

    return {
        "mode": ModeGate.current_mode().value,
        "display": display,
        "environment_hash": EnvironmentContract.fingerprint_hash(env_fp),
        "status": "BOOTSTRAP_OK",
    }


if __name__ == "__main__":
    print(bootstrap())
