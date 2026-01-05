import sys

from core.mode_gate import ModeGate, Mode
from core.poison import Poison
from core.system_state import SystemState


class BootstrapError(RuntimeError):
    pass


def _abort(reason: str) -> None:
    sys.stderr.write(f"[BOOTSTRAP ABORT] {reason}\n")
    sys.stderr.flush()
    Poison.trigger(f"bootstrap abort: {reason}")


def bootstrap(bootstrap_token) -> dict:
    """
    Stage-1 deterministic bootstrap.

    Invariants:
    - Called exactly once
    - Valid bootstrap token required
    - NO environment semantics
    - NO Stage-2 code
    - Stage-1 mode is locked here and never changes
    """

    Poison.assert_clean()

    # bootstrap token verification
    try:
        if bootstrap_token is not SystemState._token:
            _abort("invalid or stale bootstrap token")
    except BaseException:
        _abort("bootstrap token verification failed")

    # HARD LOCK MODE: STAGE_1 ONLY
    try:
        ModeGate.force(Mode.STAGE_1)
    except BaseException as e:
        _abort(f"failed to lock Stage-1 mode: {repr(e)}")

    # Return only inert, non-semantic data
    return {
        "status": "BOOTSTRAP_OK",
    }
