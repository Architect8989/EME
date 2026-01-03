import sys

from core.mode_gate import ModeGate, Mode
from core.environment_contract import EnvironmentContract
from core.poison import Poison
from core.system_state import SystemState


class BootstrapError(RuntimeError):
    pass


def hard_abort(reason: str) -> None:
    sys.stderr.write(f"[BOOTSTRAP ABORT] {reason}\n")
    sys.stderr.flush()
    raise BootstrapError(reason)


def bootstrap() -> dict:
    """
    Deterministic, executor-neutral bootstrap.
    No OS inspection.
    No signal handling.
    No environment branching.
    Single irreversible init path.
    """

    # must never run in poisoned state
    Poison.assert_clean()

    # environment contract must be explicitly verified or halt
    try:
        env_fp = EnvironmentContract.verify()
    except Exception as e:
        hard_abort(str(e))

    # exclusive bootstrap authority
    try:
        token = SystemState._issue_bootstrap_token()
        SystemState.mark_initialized(token)
    except Exception as e:
        hard_abort(f"initialization failed: {e}")

    # deterministic initial mode
    ModeGate.disarm()
    ModeGate.arm(Mode.PROBE)

    return {
        "mode": ModeGate.current_mode().value,
        "environment_hash": EnvironmentContract.fingerprint_hash(env_fp),
        "status": "BOOTSTRAP_OK",
    }
