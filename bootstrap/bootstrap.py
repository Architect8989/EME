import os
import sys
import signal

from core.mode_gate import ModeGate, Mode
from core.environment_contract import EnvironmentContract
from core.poison import Poison
from core.system_state import SystemState


def hard_abort(reason: str) -> None:
    sys.stderr.write(f"[BOOTSTRAP ABORT] {reason}\n")
    sys.stderr.flush()
    sys.exit(1)


def bootstrap() -> dict:
    # bootstrap must never run in poisoned state
    Poison.assert_clean()

    # ---- fail-closed environment checks ----
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

    # ---- terminal kill handling ----
    def _kill(_sig, _frame):
        try:
            Poison.trigger("manual kill signal received")
        finally:
            sys.exit(1)

    signal.signal(signal.SIGINT, _kill)
    signal.signal(signal.SIGTERM, _kill)

    # ---- exclusive bootstrap authority ----
    try:
        token = SystemState._issue_bootstrap_token()
        SystemState.mark_initialized(token)
    except Exception as e:
        hard_abort(f"initialization failed: {e}")

    # ---- deterministic initial authority ----
    ModeGate.disarm()
    ModeGate.arm(Mode.PROBE)

    return {
        "mode": ModeGate.current_mode().value,
        "display": display,
        "environment_hash": EnvironmentContract.fingerprint_hash(env_fp),
        "status": "BOOTSTRAP_OK",
    }


if __name__ == "__main__":
    try:
        print(bootstrap())
    except BaseException as e:
        try:
            Poison.trigger(f"bootstrap crash: {e!r}")
        finally:
            sys.exit(1)
